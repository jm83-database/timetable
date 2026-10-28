using './provision.bicep'

param location = readEnvironmentVariable('AZURE_LOCATION')
param employeeTenantId = readEnvironmentVariable('EMPLOYEE_TENANT_ID')
param mailClientId = readEnvironmentVariable('MAIL_CLIENT_ID')
