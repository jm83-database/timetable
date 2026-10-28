targetScope = 'resourceGroup'

@description('Employee tenant containing the dedicated mail application.')
param employeeTenantId string

@description('Client ID of the dedicated B-tenant Mail.Send application.')
param mailClientId string

@description('Existing timetable Cosmos DB account. It is not modified.')
param cosmosAccountName string = 'timetable-dashboard'

@description('Resource group containing the existing timetable Cosmos DB account.')
param cosmosResourceGroupName string = 'Microsoft-Academy'

@description('Start the timer only after mailbox scoping and end-to-end testing.')
param enableReminder bool = false

param location string = resourceGroup().location
param environmentName string = 'timetable-reminder'

var token = uniqueString(subscription().id, resourceGroup().id, location, environmentName)
var deploymentContainerName = 'function-package'
var blobDataOwnerRole = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'b7e6dc6d-f1e8-4753-8033-0f276bb0955b')
var secretsUserRole = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '4633458b-17de-408a-b874-0445c86b69e6')

resource cosmos 'Microsoft.DocumentDB/databaseAccounts@2024-11-15' existing = {
  name: cosmosAccountName
  scope: resourceGroup(cosmosResourceGroupName)
}

resource workerIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: 'azid${token}'
  location: location
}

resource storage 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: 'azst${token}'
  location: location
  kind: 'StorageV2'
  sku: {
    name: 'Standard_LRS'
  }
  properties: {
    allowBlobPublicAccess: false
    allowSharedKeyAccess: false
    minimumTlsVersion: 'TLS1_2'
    supportsHttpsTrafficOnly: true
  }
}

resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2023-05-01' = {
  parent: storage
  name: 'default'
}

resource deploymentContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  parent: blobService
  name: deploymentContainerName
  properties: {
    publicAccess: 'None'
  }
}

resource storageRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storage.id, workerIdentity.id, blobDataOwnerRole)
  scope: storage
  properties: {
    principalId: workerIdentity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: blobDataOwnerRole
  }
}

resource vault 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: 'azkv${token}'
  location: location
  properties: {
    tenantId: subscription().tenantId
    sku: {
      family: 'A'
      name: 'standard'
    }
    enableRbacAuthorization: true
    enableSoftDelete: true
    enablePurgeProtection: true
    softDeleteRetentionInDays: 90
  }
}

resource vaultRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(vault.id, workerIdentity.id, secretsUserRole)
  scope: vault
  properties: {
    principalId: workerIdentity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: secretsUserRole
  }
}

module cosmosRole './cosmos-role.bicep' = {
  scope: resourceGroup(cosmosResourceGroupName)
  params: {
    accountName: cosmosAccountName
    identityResourceId: workerIdentity.id
    principalId: workerIdentity.properties.principalId
  }
}

resource logs 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: 'azlog${token}'
  location: location
  properties: {
    retentionInDays: 30
    sku: {
      name: 'PerGB2018'
    }
  }
}

resource insights 'Microsoft.Insights/components@2020-02-02' = {
  name: 'azai${token}'
  location: location
  kind: 'web'
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: logs.id
  }
}

resource plan 'Microsoft.Web/serverfarms@2024-04-01' = {
  name: 'azasp${token}'
  location: location
  kind: 'functionapp'
  sku: {
    name: 'Y1'
    tier: 'Dynamic'
  }
  properties: {
    reserved: true
  }
}

resource worker 'Microsoft.Web/sites@2024-04-01' = {
  name: 'azfn${token}'
  location: location
  kind: 'functionapp,linux'
  tags: {
    app: 'timetable-reminder'
  }
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${workerIdentity.id}': {}
    }
  }
  properties: {
    serverFarmId: plan.id
    httpsOnly: true
    keyVaultReferenceIdentity: workerIdentity.id
    siteConfig: {
      minTlsVersion: '1.2'
      ftpsState: 'Disabled'
      linuxFxVersion: 'Python|3.12'
      appSettings: [
        { name: 'FUNCTIONS_EXTENSION_VERSION', value: '~4' }
        { name: 'FUNCTIONS_WORKER_RUNTIME', value: 'python' }
        { name: 'AzureWebJobsStorage__accountName', value: storage.name }
        { name: 'AzureWebJobsStorage__credential', value: 'managedidentity' }
        { name: 'AzureWebJobsStorage__clientId', value: workerIdentity.properties.clientId }
        { name: 'AZURE_CLIENT_ID', value: workerIdentity.properties.clientId }
        { name: 'WEBSITE_RUN_FROM_PACKAGE', value: '${storage.properties.primaryEndpoints.blob}${deploymentContainer.name}/current.zip' }
        { name: 'WEBSITE_RUN_FROM_PACKAGE_BLOB_MI_RESOURCE_ID', value: workerIdentity.id }
        { name: 'COSMOS_DB_ENDPOINT', value: cosmos.properties.documentEndpoint }
        { name: 'MAIL_TENANT_ID', value: employeeTenantId }
        { name: 'MAIL_CLIENT_ID', value: mailClientId }
        { name: 'MAIL_CLIENT_SECRET', value: '@Microsoft.KeyVault(SecretUri=${vault.properties.vaultUri}secrets/timetable-mail)' }
        { name: 'APPLICATIONINSIGHTS_CONNECTION_STRING', value: insights.properties.ConnectionString }
        { name: 'AzureWebJobs.reminder_timer.Disabled', value: string(!enableReminder) }
      ]
    }
  }
  dependsOn: [
    storageRole
    vaultRole
    cosmosRole
  ]
}

output functionName string = worker.name
output keyVaultName string = vault.name
output workerPrincipalId string = workerIdentity.properties.principalId
output storageAccountName string = storage.name
output packageContainerName string = deploymentContainer.name
