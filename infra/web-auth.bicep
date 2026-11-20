targetScope = 'resourceGroup'

@description('Existing production web app. Review changes and access before deployment.')
param webAppName string = 'elixirrtimetable'
param employeeTenantId string
param loginClientId string

@description('Application ID URI used as the audience for MCP access tokens. Leave empty to keep MCP disabled.')
param mcpApiAudience string = ''

@description('Application role required for timetable MCP access.')
param mcpRequiredRole string = 'Timetable.ReadWrite'

@secure()
@description('Current application settings captured immediately before deployment.')
param existingAppSettings object

@secure()
@description('Client secret for the dedicated employee sign-in application.')
param loginClientSecret string

var mcpSettings = {
  MCP_API_AUDIENCE: mcpApiAudience
  MCP_REQUIRED_ROLE: mcpRequiredRole
}

resource web 'Microsoft.Web/sites@2024-04-01' existing = {
  name: webAppName
}

resource settings 'Microsoft.Web/sites/config@2024-04-01' = {
  parent: web
  name: 'appsettings'
  properties: union(existingAppSettings, {
    TIMETABLE_AUTH_MODE: 'entra'
    EMPLOYEE_TENANT_ID: employeeTenantId
    LOGIN_CLIENT_ID: loginClientId
    LOGIN_DOMAIN: 'elixirr.co.kr'
    APP_ORIGIN: 'https://${web.properties.defaultHostName}'
    TIMETABLE_LOGIN_SECRET: loginClientSecret
  }, mcpSettings)
}

resource authentication 'Microsoft.Web/sites/config@2024-04-01' = {
  parent: web
  name: 'authsettingsV2'
  properties: {
    platform: {
      enabled: true
      runtimeVersion: '~1'
    }
    globalValidation: {
      requireAuthentication: true
      unauthenticatedClientAction: 'RedirectToLoginPage'
      redirectToProvider: 'azureactivedirectory'
    }
    identityProviders: {
      azureActiveDirectory: {
        enabled: true
        registration: {
          clientId: loginClientId
          clientSecretSettingName: 'TIMETABLE_LOGIN_SECRET'
          openIdIssuer: '${environment().authentication.loginEndpoint}${employeeTenantId}/v2.0'
        }
        validation: {
          allowedAudiences: concat([loginClientId], empty(mcpApiAudience) ? [] : [mcpApiAudience])
        }
        login: {
          loginParameters: ['scope=openid profile email offline_access']
        }
      }
    }
    login: {
      tokenStore: {
        enabled: true
      }
    }
    httpSettings: {
      requireHttps: true
    }
  }
  dependsOn: [settings]
}
