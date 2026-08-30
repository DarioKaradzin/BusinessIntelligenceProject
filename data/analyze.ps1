$csv = Import-Csv ".\data\Sample - Superstore.csv"

$customers = $csv | Select-Object -Property 'Customer ID','Customer Name','Segment' -Unique
$products = $csv | Select-Object -Property 'Product ID','Product Name','Category','Sub-Category' -Unique
$locations = $csv | Select-Object -Property 'Country','City','State','Postal Code','Region' -Unique
$orders = $csv | Select-Object -Property 'Order ID' -Unique

Write-Host "Total rows: $($csv.Count)"
Write-Host "Unique Customers: $($customers.Count)"
Write-Host "Unique Products: $($products.Count)"
Write-Host "Unique Locations: $($locations.Count)"
Write-Host "Unique Orders: $($orders.Count)"

$shipModes = $csv | ForEach-Object { $_.'Ship Mode' } | Sort-Object -Unique
Write-Host "Ship Modes: $($shipModes -join ', ')"

$segments = $csv | ForEach-Object { $_.Segment } | Sort-Object -Unique
Write-Host "Segments: $($segments -join ', ')"

$categories = $csv | ForEach-Object { $_.Category } | Sort-Object -Unique
Write-Host "Categories: $($categories -join ', ')"

$subcategories = $csv | ForEach-Object { $_.'Sub-Category' } | Sort-Object -Unique
Write-Host "Sub-Categories: $($subcategories -join ', ')"

$regions = $csv | ForEach-Object { $_.Region } | Sort-Object -Unique
Write-Host "Regions: $($regions -join ', ')"

# Date range
$dates = $csv | ForEach-Object { [DateTime]::Parse($_.'Order Date') } | Sort-Object
Write-Host "Order Date Range: $($dates[0].ToString('yyyy-MM-dd')) to $($dates[-1].ToString('yyyy-MM-dd'))"
