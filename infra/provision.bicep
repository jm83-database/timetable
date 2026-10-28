targetScope = 'subscription'

@minLength(1)
param location string

@minLength(1)
param employeeTenantId string

@minLength(1)
param mailClientId string

resource workerGroup 'Microsoft.Resources/resourceGroups@2022-09-01' = {
  name: 'rg-timetable-reminder'
  location: location
}

module worker './main.bicep' = {
  scope: workerGroup
  params: {
    location: location
    employeeTenantId: employeeTenantId
    mailClientId: mailClientId
  }
}

output AZURE_RESOURCE_GROUP string = workerGroup.name
output REMINDER_FUNCTION_NAME string = worker.outputs.functionName
output REMINDER_KEY_VAULT_NAME string = worker.outputs.keyVaultName
output REMINDER_STORAGE_ACCOUNT_NAME string = worker.outputs.storageAccountName
output REMINDER_PACKAGE_CONTAINER_NAME string = worker.outputs.packageContainerName
output REMINDER_WORKER_PRINCIPAL_ID string = worker.outputs.workerPrincipalId
