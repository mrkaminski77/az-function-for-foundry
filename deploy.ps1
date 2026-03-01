# 1) Set these
$rg = "rg-demonet-func-dev"
$app = "demonet-func-dev-app"
$zip = "deploy.zip"

# 2) (Optional) verify you are logged in and on right subscription
#az login
#az account show --output table
# az account set --subscription "<subscription-id-or-name>"

# 3) Create ZIP package (exclude local/dev artifacts)
if (Test-Path $zip) { Remove-Item $zip -Force }
Get-ChildItem -Force | Where-Object {
    $_.Name -notin @(".venv","__pycache__",".git",".python_packages","local.settings.json",$zip)
} | Compress-Archive -DestinationPath $zip -Force

# 4) Deploy ZIP to Function App
az functionapp deployment source config-zip `
  --resource-group $rg `
  --name $app `
  --src $zip

# 5) Get default host key
$key = az functionapp keys list --resource-group $rg --name $app --query "functionKeys.default" -o tsv

# 6) Open test URL
$url = "https://$app.azurewebsites.net/api/connectivity?code=$key"
$url
curl $url