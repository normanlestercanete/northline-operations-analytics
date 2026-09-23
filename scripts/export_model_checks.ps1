param([Parameter(Mandatory=$true)][int]$Port, [Parameter(Mandatory=$true)][string]$OutputPath)
$ErrorActionPreference = 'Stop'
$dllRoot = Join-Path $env:TEMP 'quantara-tom'
Add-Type -Path "$dllRoot/package/lib/net8.0/Microsoft.AnalysisServices.Core.dll"
Add-Type -Path "$dllRoot/package/lib/net8.0/Microsoft.AnalysisServices.Tabular.dll"
Add-Type -Path "$dllRoot/adomd/lib/net8.0/Microsoft.AnalysisServices.AdomdClient.dll"
$server = [Microsoft.AnalysisServices.Tabular.Server]::new()
$server.Connect("localhost:$Port")
$database = $server.Databases[0]
$errors = @($database.Model.Tables | ForEach-Object { $_.Measures | Where-Object { $_.State -ne 'Ready' } })
if ($errors.Count) { throw ($errors | Select-Object Name,ErrorMessage | ConvertTo-Json) }
$connection = [Microsoft.AnalysisServices.AdomdClient.AdomdConnection]::new("Data Source=localhost:$Port;Initial Catalog=$($database.ID)")
$connection.Open()
$command = $connection.CreateCommand()
$command.CommandText = @'
EVALUATE SUMMARIZECOLUMNS (
 'Reporting Month'[YearMonth], Warehouses[WarehouseID],
 "ShippedUnits", [Shipped Units], "InventoryValue", [Inventory Value],
 "BacklogUnits", [Backlog Units], "OverdueUnits", [Overdue Units],
 "DueOrders", [Due Orders], "DueUnits", [Due Units],
 "Fill", [Due Month Fill Rate], "OTIF", [On Time In Full],
 "Cycle", [Ship Cycle Days], "ReceivedUnits", [Received Units],
 "Lead", [Receipt Lead Days], "SupplierOTIF", [Supplier OTIF],
 "Capacity", [Stage Capacity], "Completed", [Stage Completions],
 "Wait", [Stage Wait Days], "Aged90", [Aged 90 Value],
 "PreviousShipped", [Shipped Units Previous]
)
'@
$reader = $command.ExecuteReader()
$rows = [System.Collections.Generic.List[object]]::new()
while ($reader.Read()) {
 $record = [ordered]@{}
 for ($i=0; $i -lt $reader.FieldCount; $i++) {
  $name = $reader.GetName($i) -replace '^.*\[|\]$', ''
  $record[$name] = if ($reader.IsDBNull($i)) { $null } else { $reader.GetValue($i) }
 }
 $rows.Add($record)
}
$reader.Close(); $connection.Close(); $server.Disconnect()
$rows | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $OutputPath -Encoding utf8
Write-Output "Exported $($rows.Count) monthly warehouse model checks. All measures are Ready."
