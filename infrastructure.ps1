# --- 1. Variables ---
$PROJECT = "demonet"
$SUBSCRIPTION_ID = "e6dbcc53-5170-441b-8c16-e6d1c5a3c092" 

$HUB_VNET_RG = "rg-{0}-hub-dev" -f $PROJECT
$LOC = "australiaeast"
$HUB_VNET_NAME = "{0}-hub-dev" -f $PROJECT
$VM_ZONE_NAME = "{0}-dev.vnet" -f $PROJECT
$HUB_VNET_ID = "/subscriptions/$SUBSCRIPTION_ID/resourceGroups/$HUB_VNET_RG/providers/Microsoft.Network/virtualNetworks/$HUB_VNET_NAME"

$HUB_IP_SPACE = "172.16.0.0/22"
$HUB_DEFAULT_SUBNET_SUBNET_PREFIX = "172.16.0.0/24"
$HUB_dns_resolver_inbound_SUBNET_PREFIX = "172.16.1.0/28"
$HUB_dns_resolver_inbound_address = "172.16.1.4"
$DNS_RESOLVER_NAME = "{0}-hub-dns-resolver" -f $PROJECT
$DNS_INBOUND_ENDPOINT_NAME = "{0}-hub-dns-inbound" -f $PROJECT
$DNS_SUBNET_ID = "/subscriptions/$SUBSCRIPTION_ID/resourceGroups/$HUB_VNET_RG/providers/Microsoft.Network/virtualNetworks/$HUB_VNET_NAME/subnets/dns-resolver-inbound"
$NAT_GW_NAME = "{0}-spoke-natgw" -f $PROJECT
$NAT_GW_IP_NAME = "{0}-spoke-natgw-ip" -f $PROJECT
$LB_IP_NAME = "{0}-hub-lb-ip" -f $PROJECT
$frontend_ip_name = "{0}-frontend" -f $PROJECT
$backend_pool_name = "{0}-backend-pool" -f $PROJECT
$LB_NAME = "{0}-hub-lb" -f $PROJECT
$HUB_NSG_NAME = "{0}-hub-dev-nsg" -f $PROJECT

$SPOKE_VNET_RG = "rg-{0}-spoke-dev" -f $PROJECT
$SPOKE_VNET_NAME = "{0}-spoke-dev" -f $PROJECT
$SPOKE_SUBNET_NAME = "default"
$VM_VNET_ADDRESS_SPACE = "172.17.0.0/26"
$SPOKE_NSG_NAME = "{0}-spoke-dev-nsg" -f $PROJECT
$VM_NAME = "{0}-dev-vm" -f $PROJECT
$VM_SIZE = "Standard_B2s"
$IMAGE = "Ubuntu2404"
$NIC_NAME = "{0}-dev-nic" -f $PROJECT


$FUNC_RG = "rg-{0}-func-dev" -f $PROJECT
$FUNC_VNET_NAME = "{0}-func-dev" -f $PROJECT
$FUNC_SUBNET_NAME = "func-subnet"
$FUNC_VNET_ADDRESS_SPACE = "172.19.0.0/24"
$FUNC_SUBNET_PREFIX = "172.19.0.0/25"
$FUNC_STORAGE_SUBNET_PREFIX = "172.19.0.128/25"
$FUNC_NAME = "{0}-func-dev-app" -f $PROJECT
$UAMI_NAME = "{0}-func-dev-uami" -f $PROJECT
$FUNC_STORAGE_ACCOUNT = "{0}funcdevsa" -f $PROJECT
$FUNC_NSG_NAME = "{0}-func-dev-nsg" -f $PROJECT
$FUNC_KV_NAME = "{0}-func-kv" -f $PROJECT

<#
 /$$   /$$ /$$   /$$ /$$$$$$$        /$$    /$$ /$$   /$$ /$$$$$$$$ /$$$$$$$$
| $$  | $$| $$  | $$| $$__  $$      | $$   | $$| $$$ | $$| $$_____/|__  $$__/
| $$  | $$| $$  | $$| $$  \ $$      | $$   | $$| $$$$| $$| $$         | $$   
| $$$$$$$$| $$  | $$| $$$$$$$       |  $$ / $$/| $$ $$ $$| $$$$$      | $$   
| $$__  $$| $$  | $$| $$__  $$       \  $$ $$/ | $$  $$$$| $$__/      | $$   
| $$  | $$| $$  | $$| $$  \ $$        \  $$$/  | $$\  $$$| $$         | $$   
| $$  | $$|  $$$$$$/| $$$$$$$/         \  $/   | $$ \  $$| $$$$$$$$   | $$   
|__/  |__/ \______/ |_______/           \_/    |__/  \__/|________/   |__/   
#>



az group create `
    --name $HUB_VNET_RG `
    --location $LOC `
    --subscription $SUBSCRIPTION_ID

az network vnet create `
    --subscription $SUBSCRIPTION_ID `
    --resource-group $HUB_VNET_RG `
    --name $HUB_VNET_NAME `
    --address-prefixes $HUB_IP_SPACE `
    --location $LOC

az network vnet subnet create `
    --subscription $SUBSCRIPTION_ID `
    --resource-group $HUB_VNET_RG `
    --vnet-name $HUB_VNET_NAME `
    --name "default" `
    --address-prefixes $HUB_DEFAULT_SUBNET_SUBNET_PREFIX

az network vnet subnet create `
    --subscription $SUBSCRIPTION_ID `
    --resource-group $HUB_VNET_RG `
    --vnet-name $HUB_VNET_NAME `
    --name "dns-resolver-inbound" `
    --address-prefixes $HUB_dns_resolver_inbound_SUBNET_PREFIX

az dns-resolver create `
    --resource-group $HUB_VNET_RG `
    --name $DNS_RESOLVER_NAME `
    --location $LOC `
    --id $HUB_VNET_ID `
    --subscription $SUBSCRIPTION_ID

$configObject = ,@(
    @{
        "private-ip-allocation-method" = "Dynamic"
            "id" = $DNS_SUBNET_ID
    }
)
$ip_config = $configObject | ConvertTo-Json -Compress -Depth 3
az dns-resolver inbound-endpoint create `
    --resource-group $HUB_VNET_RG `
    --dns-resolver-name $DNS_RESOLVER_NAME `
    --name $DNS_INBOUND_ENDPOINT_NAME `
    --location $LOC `
    --ip-configurations $ip_config `
    --subscription $SUBSCRIPTION_ID


# List of Private Link Zones (No Auto-Registration)
$privateLinkZones = @(
    "privatelink.blob.core.windows.net",
    "privatelink.table.core.windows.net",
    "privatelink.queue.core.windows.net",
    "privatelink.dfs.core.windows.net",
    "privatelink.file.core.windows.net",
    "privatelink.sql.azuresynapse.net",
    "privatelink.ondemand.sql.azuresynapse.net",
    "privatelink.dev.azuresynapse.net",
    "privatelink.vaultcore.azure.net",
    "privatelink.azurewebsites.net",
    "privatelink.services.ai.azure.com",
    "privatelink.cognitiveservices.azure.com",
    "privatelink.openai.azure.com",
    "privatelink.api.azureml.ms",
    "privatelink.notebooks.azure.net",
    "privatelink.dev.azure.com",
    "privatelink.visualstudio.com",

    "privatelink.monitor.azure.com",
    "privatelink.oms.opinsights.azure.com",
    "privatelink.ods.opinsights.azure.com",
    "privatelink.agentsvc.azure.com"
)

# 2. Get the VNet reference once
$vnet = (az network vnet show `
    --resource-group $HUB_VNET_RG `
    --name $HUB_VNET_NAME `
    --subscription $SUBSCRIPTION_ID | ConvertFrom-Json).id

foreach ($zone in $privateLinkZones) {
    az network private-dns zone create `
        --resource-group $HUB_VNET_RG `
        --name $zone `
        --subscription $SUBSCRIPTION_ID

    az network private-dns link vnet create `
        --resource-group $HUB_VNET_RG `
        --zone-name $zone `
        --name "link-$zone" `
        --virtual-network $vnet `
        --registration-enabled false `
        --subscription $SUBSCRIPTION_ID
}

# Create VM zone with auto-registration enabled
az network private-dns zone create `
    --resource-group $HUB_VNET_RG `
    --name $VM_ZONE_NAME `
    --subscription $SUBSCRIPTION_ID

az network private-dns link vnet create `
    --resource-group $HUB_VNET_RG `
    --zone-name $VM_ZONE_NAME `
    --name "link-$VM_ZONE_NAME" `
    --virtual-network $vnet `
    --registration-enabled true `
    --subscription $SUBSCRIPTION_ID


az network public-ip create `
    --resource-group $HUB_VNET_RG `
    --name $NAT_GW_IP_NAME `
    --sku Standard `
    --allocation-method Static `
    --subscription $SUBSCRIPTION_ID

az network nat gateway create `
    --resource-group $HUB_VNET_RG `
    --name $NAT_GW_NAME `
    --public-ip-addresses $NAT_GW_IP_NAME `
    --subscription $SUBSCRIPTION_ID

az network public-ip create `
    --resource-group $HUB_VNET_RG `
    --name $LB_IP_NAME `
    --sku Standard `
    --allocation-method Static `
    --subscription $SUBSCRIPTION_ID

az network lb create `
    --resource-group $HUB_VNET_RG `
    --name $LB_NAME `
    --sku Standard `
    --public-ip-address $LB_IP_NAME `
    --frontend-ip-name $frontend_ip_name `
    --backend-pool-name $backend_pool_name `
    --subscription $SUBSCRIPTION_ID

az network nsg create `
    --resource-group $HUB_VNET_RG `
    --name $HUB_NSG_NAME `
    --subscription $SUBSCRIPTION_ID





az monitor private-link-scope create `
    --resource-group $HUB_VNET_RG `
    --name "$PROJECT-ampls"

$law_id = (az monitor log-analytics workspace create `
    --resource-group $HUB_VNET_RG `
    --workspace-name "$PROJECT-law" `
    --location $LOC `
    --subscription $SUBSCRIPTION_ID | ConvertFrom-Json).id

az monitor log-analytics workspace update `
    --resource-group $HUB_VNET_RG `
    --workspace-name "$PROJECT-law" `
    --ingestion-access Disabled `
    --query-access Disabled `
    --subscription $SUBSCRIPTION_ID

az monitor private-link-scope scoped-resource create `
    --name "$PROJECT-law" `
    --resource-group $HUB_VNET_RG `
    --scope-name "$PROJECT-ampls" `
    --linked-resource $law_id `
    --subscription $SUBSCRIPTION_ID

$ampls_id = (az monitor private-link-scope show `
    --resource-group $HUB_VNET_RG `
    --name "$PROJECT-ampls" `
    --subscription $SUBSCRIPTION_ID | ConvertFrom-Json).id

$pename = "{0}-ampls-pe" -f $PROJECT
az network private-endpoint create `
    --resource-group $HUB_VNET_RG `
    --name $pename `
    --connection-name "$pename-azuremonitor" `
    --vnet-name $HUB_VNET_NAME `
    --subnet "default" `
    --private-connection-resource-id $ampls_id `
    --group-id azuremonitor `
    --subscription $SUBSCRIPTION_ID

$HUB_MONITOR_ZONE_ID = "/subscriptions/$SUBSCRIPTION_ID/resourceGroups/$HUB_VNET_RG/providers/Microsoft.Network/privateDnsZones/privatelink.monitor.azure.com"
$HUB_OMS_ZONE_ID = "/subscriptions/$SUBSCRIPTION_ID/resourceGroups/$HUB_VNET_RG/providers/Microsoft.Network/privateDnsZones/privatelink.oms.opinsights.azure.com"
$HUB_ODS_ZONE_ID = "/subscriptions/$SUBSCRIPTION_ID/resourceGroups/$HUB_VNET_RG/providers/Microsoft.Network/privateDnsZones/privatelink.ods.opinsights.azure.com"
$HUB_AGENTSVC = "/subscriptions/$SUBSCRIPTION_ID/resourceGroups/$HUB_VNET_RG/providers/Microsoft.Network/privateDnsZones/privatelink.agentsvc.azure.com"
$HUB_BLOB_ZONE_ID = "/subscriptions/$SUBSCRIPTION_ID/resourceGroups/$HUB_VNET_RG/providers/Microsoft.Network/privateDnsZones/privatelink.blob.core.windows.net"

az network private-endpoint dns-zone-group create `
    --resource-group $HUB_VNET_RG `
    --endpoint-name $pename `
    --name "ampls-dns-zone-group" `
    --zone-name "monitor" --private-dns-zone $HUB_MONITOR_ZONE_ID `
    --subscription $SUBSCRIPTION_ID    

az network private-endpoint dns-zone-group create `
    --resource-group $HUB_VNET_RG `
    --endpoint-name $pename `
    --name "ampls-dns-zone-group" `
    --zone-name "oms" --private-dns-zone $HUB_OMS_ZONE_ID `
    --subscription $SUBSCRIPTION_ID    

az network private-endpoint dns-zone-group create `
    --resource-group $HUB_VNET_RG `
    --endpoint-name $pename `
    --name "ampls-dns-zone-group" `
    --subscription $SUBSCRIPTION_ID `
    --zone-name "ods" --private-dns-zone $HUB_ODS_ZONE_ID

az network private-endpoint dns-zone-group create `
    --resource-group $HUB_VNET_RG `
    --endpoint-name $pename `
    --name "ampls-dns-zone-group" `
    --subscription $SUBSCRIPTION_ID `
    --zone-name "agentsvc" --private-dns-zone $HUB_AGENTSVC

az network private-endpoint dns-zone-group create `
    --resource-group $HUB_VNET_RG `
    --endpoint-name $pename `
    --name "ampls-dns-zone-group" `
    --subscription $SUBSCRIPTION_ID `
    --zone-name "blob" --private-dns-zone $HUB_BLOB_ZONE_ID

# Enable diagnostics on hub resource group resources
$law_name = "$PROJECT-law"

# Enable diagnostics on NAT Gateway
az monitor diagnostic-settings create `
    --name "natgw-diagnostics" `
    --resource "/subscriptions/$SUBSCRIPTION_ID/resourceGroups/$HUB_VNET_RG/providers/Microsoft.Network/natGateways/$NAT_GW_NAME" `
    --workspace $law_name `
    --resource-group $HUB_VNET_RG `
    --metrics '[{"category":"AllMetrics","enabled":true}]' `
    --subscription $SUBSCRIPTION_ID

# Enable diagnostics on Load Balancer
az monitor diagnostic-settings create `
    --name "lb-diagnostics" `
    --resource "/subscriptions/$SUBSCRIPTION_ID/resourceGroups/$HUB_VNET_RG/providers/Microsoft.Network/loadBalancers/$LB_NAME" `
    --workspace $law_name `
    --resource-group $HUB_VNET_RG `
    --logs '[{"category":"LoadBalancerHealthEvent","enabled":true}]' `
    --metrics '[{"category":"AllMetrics","enabled":true}]' `
    --subscription $SUBSCRIPTION_ID

# Enable diagnostics on NSG
az monitor diagnostic-settings create `
    --name "nsg-diagnostics" `
    --resource "/subscriptions/$SUBSCRIPTION_ID/resourceGroups/$HUB_VNET_RG/providers/Microsoft.Network/networkSecurityGroups/$HUB_NSG_NAME" `
    --workspace $law_name `
    --resource-group $HUB_VNET_RG `
    --logs '[{"category":"NetworkSecurityGroupEvent","enabled":true},{"category":"NetworkSecurityGroupRuleCounter","enabled":true}]' `
    --subscription $SUBSCRIPTION_ID



 <#   
 /$$    /$$ /$$      /$$       /$$    /$$ /$$   /$$ /$$$$$$$$ /$$$$$$$$
| $$   | $$| $$$    /$$$      | $$   | $$| $$$ | $$| $$_____/|__  $$__/
| $$   | $$| $$$$  /$$$$      | $$   | $$| $$$$| $$| $$         | $$   
|  $$ / $$/| $$ $$/$$ $$      |  $$ / $$/| $$ $$ $$| $$$$$      | $$   
 \  $$ $$/ | $$  $$$| $$       \  $$ $$/ | $$  $$$$| $$__/      | $$   
  \  $$$/  | $$\  $ | $$        \  $$$/  | $$\  $$$| $$         | $$   
   \  $/   | $$ \/  | $$         \  $/   | $$ \  $$| $$$$$$$$   | $$   
    \_/    |__/     |__/          \_/    |__/  \__/|________/   |__/   
#>                                                                    

# Create Spoke VNET for Developer VMs


az group create `
    --name $SPOKE_VNET_RG `
    --location $LOC `
    --subscription $SUBSCRIPTION_ID

az network vnet create `
    --subscription $SUBSCRIPTION_ID `
    --resource-group $SPOKE_VNET_RG `
    --name $SPOKE_VNET_NAME `
    --address-prefixes $VM_VNET_ADDRESS_SPACE `
    --location $LOC `
    --dns-servers $HUB_dns_resolver_inbound_address `
    --subscription $SUBSCRIPTION_ID

az network nsg create `
    --resource-group $SPOKE_VNET_RG `
    --name $SPOKE_NSG_NAME `
    --subscription $SUBSCRIPTION_ID

az network vnet subnet create `
    --subscription $SUBSCRIPTION_ID `
    --resource-group $SPOKE_VNET_RG `
    --vnet-name $SPOKE_VNET_NAME `
    --name $SPOKE_SUBNET_NAME `
    --address-prefixes $VM_VNET_ADDRESS_SPACE `
    --network-security-group $SPOKE_NSG_NAME

az network nic create `
    --resource-group $SPOKE_VNET_RG `
    --name $NIC_NAME `
    --vnet-name $SPOKE_VNET_NAME `
    --subnet $SPOKE_SUBNET_NAME `
    --subscription $SUBSCRIPTION_ID

az vm create `
    --resource-group $SPOKE_VNET_RG `
    --name $VM_NAME `
    --nics $NIC_NAME `
    --image $IMAGE `
    --size $VM_SIZE `
    --admin-username azureuser `
    --generate-ssh-keys `
	--assign-identity `
    --subscription $SUBSCRIPTION_ID

az network vnet peering create `
    --resource-group $HUB_VNET_RG `
    --vnet-name $HUB_VNET_NAME `
    --name "hub-to-vm-spoke" `
    --remote-vnet "/subscriptions/$SUBSCRIPTION_ID/resourceGroups/$SPOKE_VNET_RG/providers/Microsoft.Network/virtualNetworks/$SPOKE_VNET_NAME" `
    --allow-vnet-access `
    --allow-forwarded-traffic `
    --subscription $SUBSCRIPTION_ID

az network vnet peering create `
    --resource-group $SPOKE_VNET_RG `
    --vnet-name $SPOKE_VNET_NAME `
    --name "vm-spoke-to-hub" `
    --remote-vnet "/subscriptions/$SUBSCRIPTION_ID/resourceGroups/$HUB_VNET_RG/providers/Microsoft.Network/virtualNetworks/$HUB_VNET_NAME" `
    --allow-vnet-access `
    --allow-forwarded-traffic `
    --subscription $SUBSCRIPTION_ID

$backendPoolId = "/subscriptions/$SUBSCRIPTION_ID/resourceGroups/$HUB_VNET_RG/providers/Microsoft.Network/loadBalancers/$LB_NAME/backendAddressPools/$backend_pool_name"
az network nic ip-config address-pool add `
    --resource-group $SPOKE_VNET_RG `
    --nic-name $NIC_NAME `
    --ip-config-name ipconfig1 `
    --address-pool $backendPoolId `
    --subscription $SUBSCRIPTION_ID


# Define inbound NSG rules for the spoke
$spoke_inbound_rules = @(
    @{ Name = "allow-ssh-inbound1"; Priority = 100; Direction = "Inbound"; Access = "Allow"; Protocol = "Tcp"; Src = "52.187.212.18/32"; SrcPort = "*"; Dest = "*"; DestPort = "22" },
    @{ Name = "allow-ssh-inbound2"; Priority = 110; Direction = "Inbound"; Access = "Allow"; Protocol = "Tcp"; Src = "52.237.239.53/32"; SrcPort = "*"; Dest = "*"; DestPort = "22" }
)

foreach ($rule in $spoke_inbound_rules) {
    az network nsg rule create `
        --resource-group $SPOKE_VNET_RG `
        --nsg-name $SPOKE_NSG_NAME `
        --name $rule.Name `
        --priority $rule.Priority `
        --direction $rule.Direction `
        --access $rule.Access `
        --protocol $rule.Protocol `
        --source-address-prefixes $rule.Src `
        --source-port-ranges $rule.SrcPort `
        --destination-address-prefixes $rule.Dest `
        --destination-port-ranges $rule.DestPort `
        --subscription $SUBSCRIPTION_ID
}

# Create inbound NAT rule on load balancer to forward port 22 to VM

$natRuleId = (az network lb inbound-nat-rule create `
    --resource-group $HUB_VNET_RG `
    --lb-name $LB_NAME `
    --name "nat-rule-ssh" `
    --protocol tcp `
    --frontend-port 22 `
    --backend-port 22 `
    --frontend-ip-name $frontend_ip_name `
    --subscription $SUBSCRIPTION_ID | ConvertFrom-Json).id

az network nic ip-config inbound-nat-rule add `
    --resource-group $SPOKE_VNET_RG `
    --nic-name $NIC_NAME `
    --ip-config-name ipconfig1 `
    --inbound-nat-rule $natRuleId `
    --subscription $SUBSCRIPTION_ID

# Get NAT Gateway resource ID for cross-resource group associations
$NAT_GW_ID = "/subscriptions/$SUBSCRIPTION_ID/resourceGroups/$HUB_VNET_RG/providers/Microsoft.Network/natGateways/$NAT_GW_NAME"

# Associate NAT Gateway with spoke subnet for internet access
az network vnet subnet update `
    --resource-group $SPOKE_VNET_RG `
    --vnet-name $SPOKE_VNET_NAME `
    --name $SPOKE_SUBNET_NAME `
    --nat-gateway $NAT_GW_ID `
    --subscription $SUBSCRIPTION_ID        

<#
sudo apt update
# Install MATE core and the browser
sudo apt install -y mate-desktop-environment-core firefox xrdp
sudo apt install -y mate-applet-brisk-menu 
sudo apt install -y mate-applets-common
# Set MATE as the session for your user
echo "mate-session" > ~/.xsessionecho "mate-session" > ~/.xsession

# Add xrdp to the ssl-cert group so it can read certificates
sudo adduser xrdp ssl-cert

# Restart the service
sudo systemctl restart xrdp


sudo nano /etc/xrdp/startwm.sh
## Add the following lines before the last line (which executes the session):
## unset DBUS_SESSION_BUS_ADDRESS
## unset SESSION_MANAGER

ssh -N -L 33389:localhost:3389 youruser@your-vm-ip
#>
<#
if there are problems signing in to the xSession check
sudo tail -f /var/log/auth.log

#>

az monitor diagnostic-settings create `
    --name "nsg-diagnostics" `
    --resource "/subscriptions/$SUBSCRIPTION_ID/resourceGroups/$SPOKE_VNET_RG/providers/Microsoft.Compute/virtualMachines/$VM_NAME" `
    --workspace $law_name `
    --resource-group $HUB_VNET_RG `
    --metrics '[{"category":"AllMetrics","enabled":true}]' `
    --subscription $SUBSCRIPTION_ID



<#
 /$$$$$$$$ /$$   /$$ /$$   /$$  /$$$$$$  /$$$$$$$$ /$$$$$$  /$$$$$$  /$$   /$$       /$$    /$$ /$$   /$$ /$$$$$$$$ /$$$$$$$$
| $$_____/| $$  | $$| $$$ | $$ /$$__  $$|__  $$__/|_  $$_/ /$$__  $$| $$$ | $$      | $$   | $$| $$$ | $$| $$_____/|__  $$__/
| $$      | $$  | $$| $$$$| $$| $$  \__/   | $$     | $$  | $$  \ $$| $$$$| $$      | $$   | $$| $$$$| $$| $$         | $$   
| $$$$$   | $$  | $$| $$ $$ $$| $$         | $$     | $$  | $$  | $$| $$ $$ $$      |  $$ / $$/| $$ $$ $$| $$$$$      | $$   
| $$__/   | $$  | $$| $$  $$$$| $$         | $$     | $$  | $$  | $$| $$  $$$$       \  $$ $$/ | $$  $$$$| $$__/      | $$   
| $$      | $$  | $$| $$\  $$$| $$    $$   | $$     | $$  | $$  | $$| $$\  $$$        \  $$$/  | $$\  $$$| $$         | $$   
| $$      |  $$$$$$/| $$ \  $$|  $$$$$$/   | $$    /$$$$$$|  $$$$$$/| $$ \  $$         \  $/   | $$ \  $$| $$$$$$$$   | $$   
|__/       \______/ |__/  \__/ \______/    |__/   |______/ \______/ |__/  \__/          \_/    |__/  \__/|________/   |__/   
#>

# Create Resource Group for Azure Function (Flex Consumption)


az group create `
    --name $FUNC_RG `
    --location $LOC `
    --subscription $SUBSCRIPTION_ID

# Create VNet for Azure Function (172.19.0.0/24)
az network vnet create `
    --subscription $SUBSCRIPTION_ID `
    --resource-group $FUNC_RG `
    --name $FUNC_VNET_NAME `
    --address-prefixes $FUNC_VNET_ADDRESS_SPACE `
    --location $LOC `
    --dns-servers $HUB_dns_resolver_inbound_address


# Create subnet delegated to Microsoft.App/environments for Flex Consumption Plan
az network vnet subnet create `
    --subscription $SUBSCRIPTION_ID `
    --resource-group $FUNC_RG `
    --vnet-name $FUNC_VNET_NAME `
    --name $FUNC_SUBNET_NAME `
    --address-prefixes $FUNC_SUBNET_PREFIX `
    --delegations Microsoft.App/environments



az network nsg create `
    --resource-group $FUNC_RG `
    --name $FUNC_NSG_NAME `
    --subscription $SUBSCRIPTION_ID

az network vnet subnet update `
    --resource-group $FUNC_RG `
    --vnet-name $FUNC_VNET_NAME `
    --name $FUNC_SUBNET_NAME `
    --network-security-group $FUNC_NSG_NAME `
    --subscription $SUBSCRIPTION_ID

## we will need to create another nat gateway in this vnet and in the future we should change the other nat gateway to the spoke vnet
$NAT_GW_ID = "/subscriptions/$SUBSCRIPTION_ID/resourceGroups/$HUB_VNET_RG/providers/Microsoft.Network/natGateways/$NAT_GW_NAME"
az network vnet subnet update `
    --resource-group $FUNC_RG `
    --vnet-name $FUNC_VNET_NAME `
    --name $FUNC_SUBNET_NAME `
    --nat-gateway $NAT_GW_ID `
    --subscription $SUBSCRIPTION_ID

az network vnet peering create `
    --resource-group $HUB_VNET_RG `
    --vnet-name $HUB_VNET_NAME `
    --name "hub-to-func" `
    --remote-vnet "/subscriptions/$SUBSCRIPTION_ID/resourceGroups/$FUNC_RG/providers/Microsoft.Network/virtualNetworks/$FUNC_VNET_NAME" `
    --allow-vnet-access `
    --allow-forwarded-traffic `
    --subscription $SUBSCRIPTION_ID

az network vnet peering create `
    --resource-group $FUNC_RG `
    --vnet-name $FUNC_VNET_NAME `
    --name "func-to-hub" `
    --remote-vnet "/subscriptions/$SUBSCRIPTION_ID/resourceGroups/$HUB_VNET_RG/providers/Microsoft.Network/virtualNetworks/$HUB_VNET_NAME" `
    --allow-vnet-access `
    --allow-forwarded-traffic `
    --subscription $SUBSCRIPTION_ID

az network vnet peering create `
    --resource-group $SPOKE_VNET_RG `
    --vnet-name $SPOKE_VNET_NAME `
    --name "spoke-to-func" `
    --remote-vnet "/subscriptions/$SUBSCRIPTION_ID/resourceGroups/$FUNC_RG/providers/Microsoft.Network/virtualNetworks/$FUNC_VNET_NAME" `
    --allow-vnet-access `
    --allow-forwarded-traffic `
    --subscription $SUBSCRIPTION_ID

az network vnet peering create `
    --resource-group $FUNC_RG `
    --vnet-name $FUNC_VNET_NAME `
    --name "func-to-spoke" `
    --remote-vnet "/subscriptions/$SUBSCRIPTION_ID/resourceGroups/$SPOKE_VNET_RG/providers/Microsoft.Network/virtualNetworks/$SPOKE_VNET_NAME" `
    --allow-vnet-access `
    --allow-forwarded-traffic `
    --subscription $SUBSCRIPTION_ID

## not good
$funcNsgOutboundRules = @(
    @{ Name = "allow-Entra"; Priority = 105; Dest = "AzureActiveDirectory"; Access = "Allow" },
    @{ Name = "deny-all-outbound"; Priority = 200; Dest = "*"; Access = "Deny" }
)

foreach ($rule in $funcNsgOutboundRules) {
    az network nsg rule create `
        --resource-group $FUNC_RG `
        --nsg-name $FUNC_NSG_NAME `
        --name $rule.Name `
        --priority $rule.Priority `
        --direction Outbound `
        --access $rule.Access `
        --protocol '*' `
        --source-address-prefixes '*' `
        --source-port-ranges '*' `
        --destination-address-prefixes $rule.Dest `
        --destination-port-ranges '*' `
        --subscription $SUBSCRIPTION_ID
}

az network vnet subnet create `
    --subscription $SUBSCRIPTION_ID `
    --resource-group $FUNC_RG `
    --vnet-name $FUNC_VNET_NAME `
    --name "storage-subnet" `
    --address-prefixes $FUNC_STORAGE_SUBNET_PREFIX `
    --network-security-group $FUNC_NSG_NAME


az identity create `
    --resource-group $FUNC_RG `
    --name $UAMI_NAME `
    --subscription $SUBSCRIPTION_ID

az storage account create `
    --resource-group $FUNC_RG `
    --name $FUNC_STORAGE_ACCOUNT `
    --location $LOC `
    --sku Standard_LRS `
    --allow-blob-public-access false `
    --public-network-access Disabled `
    --bypass None `
    --subscription $SUBSCRIPTION_ID `
    --default-action Deny

$blobpename = "{0}-func-blob-pe" -f $PROJECT
az network private-endpoint create `
    --resource-group $FUNC_RG `
    --name $blobpename `
    --connection-name "$blobpename-blob" `
    --vnet-name $FUNC_VNET_NAME `
    --subnet "storage-subnet" `
    --private-connection-resource-id "/subscriptions/$SUBSCRIPTION_ID/resourceGroups/$FUNC_RG/providers/Microsoft.Storage/storageAccounts/$FUNC_STORAGE_ACCOUNT" `
    --group-id blob `
    --subscription $SUBSCRIPTION_ID

$tablepename = "{0}-func-table-pe" -f $PROJECT
az network private-endpoint create `
    --resource-group $FUNC_RG `
    --name $tablepename `
    --connection-name "$tablepename-table" `
    --vnet-name $FUNC_VNET_NAME `
    --subnet "storage-subnet" `
    --private-connection-resource-id "/subscriptions/$SUBSCRIPTION_ID/resourceGroups/$FUNC_RG/providers/Microsoft.Storage/storageAccounts/$FUNC_STORAGE_ACCOUNT" `
    --group-id table `
    --subscription $SUBSCRIPTION_ID    

$HUB_BLOB_ZONE_ID = "/subscriptions/$SUBSCRIPTION_ID/resourceGroups/$HUB_VNET_RG/providers/Microsoft.Network/privateDnsZones/privatelink.blob.core.windows.net"
az network private-endpoint dns-zone-group create `
    --resource-group $FUNC_RG `
    --endpoint-name $blobpename `
    --name "blob-dns-zone-group" `
    --zone-name "blob" `
    --private-dns-zone $HUB_BLOB_ZONE_ID `
    --subscription $SUBSCRIPTION_ID

$HUB_TABLE_ZONE_ID = "/subscriptions/$SUBSCRIPTION_ID/resourceGroups/$HUB_VNET_RG/providers/Microsoft.Network/privateDnsZones/privatelink.table.core.windows.net"    
az network private-endpoint dns-zone-group create `
    --resource-group $FUNC_RG `
    --endpoint-name $tablepename `
    --name "table-dns-zone-group" `
    --zone-name "table" `
    --private-dns-zone $HUB_TABLE_ZONE_ID `
    --subscription $SUBSCRIPTION_ID

$UAMI_ID = (az identity show `
    --resource-group $FUNC_RG `
    --name $UAMI_NAME `
    --subscription $SUBSCRIPTION_ID | ConvertFrom-Json).principalId

$STORAGE_ID = (az storage account show `
    --resource-group $FUNC_RG `
    --name $FUNC_STORAGE_ACCOUNT `
    --subscription $SUBSCRIPTION_ID | ConvertFrom-Json).id

az role assignment create `
    --assignee-object-id $UAMI_ID `
    --role "Storage Blob Data Owner" `
    --scope $STORAGE_ID `
    --assignee-principal-type ServicePrincipal `
    --subscription $SUBSCRIPTION_ID

az role assignment create `
    --assignee-object-id $UAMI_ID `
    --role "Storage Table Data Contributor" `
    --scope $STORAGE_ID `
    --assignee-principal-type ServicePrincipal `
    --subscription $SUBSCRIPTION_ID

az keyvault create `
    --name $FUNC_KV_NAME `
    --resource-group $FUNC_RG `
    --location $LOC `
    --subscription $SUBSCRIPTION_ID `
    --public-network-access Disabled `
    --bypass None

$keyvaultpename = "{0}-func-kv-pe" -f $PROJECT    
az network private-endpoint create `
    --resource-group $FUNC_RG `
    --name $keyvaultpename `
    --connection-name "$keyvaultpename-conn" `
    --vnet-name $FUNC_VNET_NAME `
    --subnet "storage-subnet" `
    --private-connection-resource-id "/subscriptions/$SUBSCRIPTION_ID/resourceGroups/$FUNC_RG/providers/Microsoft.KeyVault/vaults/$FUNC_KV_NAME" `
    --group-id vault `
    --subscription $SUBSCRIPTION_ID

$KV_ZONE_ID = "/subscriptions/$SUBSCRIPTION_ID/resourceGroups/$HUB_VNET_RG/providers/Microsoft.Network/privateDnsZones/privatelink.vaultcore.azure.net" 
az network private-endpoint dns-zone-group create `
    --resource-group $FUNC_RG `
    --endpoint-name $keyvaultpename `
    --name "kv-dns-zone-group" `
    --zone-name "vault" `
    --private-dns-zone $KV_ZONE_ID `
    --subscription $SUBSCRIPTION_ID

az role assignment create `
    --assignee-object-id $UAMI_ID `
    --role "Key Vault Secrets User" `
    --scope "/subscriptions/$SUBSCRIPTION_ID/resourceGroups/$FUNC_RG/providers/Microsoft.KeyVault/vaults/$FUNC_KV_NAME" `
    --assignee-principal-type ServicePrincipal `
    --subscription $SUBSCRIPTION_ID

$uami_resource_id = "/subscriptions/$SUBSCRIPTION_ID/resourceGroups/$FUNC_RG/providers/Microsoft.ManagedIdentity/userAssignedIdentities/$UAMI_NAME"
az functionapp create `
    --resource-group $FUNC_RG `
    --name  $FUNC_NAME `
    --storage-account $FUNC_STORAGE_ACCOUNT `
    --functions-version 4 `
    --runtime python `
    --runtime-version 3.14 `
    --vnet $FUNC_VNET_NAME `
    --subnet $FUNC_SUBNET_NAME `
    --subscription $SUBSCRIPTION_ID `
    --disable-app-insights `
    --flexconsumption-location $LOC `
    --assign-identity $uami_resource_id "[system]" `
    --public-network-access Disabled

$function_msi_id=$(az functionapp identity show `
    --name $FUNC_NAME `
    --resource-group $FUNC_RG `
    --subscription $SUBSCRIPTION_ID | ConvertFrom-Json).principalId

az role assignment create `
    --assignee-object-id $function_msi_id `
    --role "Storage Blob Data Owner" `
    --scope $STORAGE_ID `
    --assignee-principal-type ServicePrincipal `
    --subscription $SUBSCRIPTION_ID

az role assignment create `
    --assignee-object-id $function_msi_id `
    --role "Storage Table Data Contributor" `
    --scope $STORAGE_ID `
    --assignee-principal-type ServicePrincipal `
    --subscription $SUBSCRIPTION_ID

az role assignment create `
    --assignee-object-id $function_msi_id `
    --role "Key Vault Secrets User" `
    --scope "/subscriptions/$SUBSCRIPTION_ID/resourceGroups/$FUNC_RG/providers/Microsoft.KeyVault/vaults/$FUNC_KV_NAME" `
    --assignee-principal-type ServicePrincipal `
    --subscription $SUBSCRIPTION_ID


az functionapp deployment config set `
    --name $FUNC_NAME `
    --resource-group $FUNC_RG `
    --deployment-storage-name $FUNC_STORAGE_ACCOUNT `
    --deployment-storage-container-name "app-package-demonetfuncdevapp-9501593" `
    --deployment-storage-auth-type UserAssignedIdentity `
    --deployment-storage-auth-value $uami_resource_id

az functionapp config appsettings set `
    --name $FUNC_NAME `
    --resource-group $FUNC_RG `
    --settings "AzureWebJobsStorage__accountName=$FUNC_STORAGE_ACCOUNT" `
        "KEY_VAULT_URL=https://$FUNC_KV_NAME.vault.azure.net/" `
        "KEY_VAULT_SECRET_NAME=demo-secret" `
        "AZURE_AI_PROJECT_ENDPOINT=https://$PROJECT.openai.azure.com/" `
        "ENTRA_TEST_SCOPE=https://graph.microsoft.com/.default" `
        "GRAPH_API_URL=https://graph.microsoft.com/v1.0" `
        "STORAGE_ACCOUNT_URL=https://$FUNC_STORAGE_ACCOUNT.blob.core.windows.net/" `
        --subscription $SUBSCRIPTION_ID

$func_pename = "{0}-func-secret-pe" -f $PROJECT
$func_resource_id = "/subscriptions/$SUBSCRIPTION_ID/resourceGroups/$FUNC_RG/providers/Microsoft.Web/sites/$FUNC_NAME"
az network private-endpoint create `
    --resource-group $FUNC_RG `
    --name $func_pename `
    --connection-name "$func_pename-conn" `
    --vnet-name $FUNC_VNET_NAME `
    --subnet "storage-subnet" `
    --private-connection-resource-id $func_resource_id `
    --group-id sites `
    --subscription $SUBSCRIPTION_ID

$FUNC_ZONE_ID = "/subscriptions/$SUBSCRIPTION_ID/resourceGroups/$HUB_VNET_RG/providers/Microsoft.Network/privateDnsZones/privatelink.azurewebsites.net"
az network private-endpoint dns-zone-group create `
    --resource-group $FUNC_RG `
    --endpoint-name $func_pename `
    --name "func-secret-dns-zone-group" `
    --zone-name "sites" `
    --private-dns-zone $FUNC_ZONE_ID `
    --subscription $SUBSCRIPTION_ID

az functionapp config appsettings set `
     --name $FUNC_NAME `
     --resource-group $FUNC_RG `
     --settings "AzureWebJobsStorage__accountName=$FUNC_STORAGE_ACCOUNT" `
         "KEY_VAULT_URL=https://$FUNC_KV_NAME.vault.azure.net/" `
         "KEY_VAULT_SECRET_NAME=ai-foundry-key" `
         "AZURE_AI_FOUNDRY_ENDPOINT=https://sra1d-foundry-01.services.ai.azure.com/" `
         "AZURE_AI_FOUNDRY_PROJECT=proj-default" `
         "AZURE_AI_FOUNDRY_AGENT=asst_jvXRZdimLpqYRb9PrO72tPXp" `
         "ENTRA_TEST_SCOPE=https://graph.microsoft.com/.default" `
         "GRAPH_API_URL=https://graph.microsoft.com/v1.0" `
         "STORAGE_ACCOUNT_URL=https://$FUNC_STORAGE_ACCOUNT.blob.core.windows.net/" `
         "AUSTENDER_OCDS_URL=https://api.tenders.gov.au/" `
         --subscription $SUBSCRIPTION_ID


# the below script may need to be made from a service that can see the endpoints
# or temporarily allow public access

$AI_FOUNDRY_NAME = "sra1d-foundry-01"
$AI_FOUNDRY_RG = "SRA1D-RG-FOUNDRY"

$AI_KEY = (az cognitiveservices account keys list `
    --name $AI_FOUNDRY_NAME `
    --resource-group $AI_FOUNDRY_RG `
    --subscription $SUBSCRIPTION_ID | ConvertFrom-Json).key1

az keyvault secret set `
    --vault-name $FUNC_KV_NAME `
    --name "ai-foundry-key" `
    --value $AI_KEY `
    --subscription $SUBSCRIPTION_ID

az monitor diagnostic-settings create `
    --name "funcapp-diagnostics" `
    --resource "/subscriptions/$SUBSCRIPTION_ID/resourceGroups/$FUNC_RG/providers/Microsoft.Web/sites/$FUNC_NAME" `
    --workspace $law_name `
    --resource-group $HUB_VNET_RG `
    --logs '[{"category":"FunctionAppLogs","enabled":true},{"category":"AppServiceAuditLogs","enabled":true},{"category":"AppServiceIPSecAuditLogs","enabled":true}]' `
    --metrics '[{"category":"AllMetrics","enabled":true}]' `
    --subscription $SUBSCRIPTION_ID
