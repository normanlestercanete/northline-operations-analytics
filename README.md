# Northline Supply — Operations & Inventory Analytics

A fictional US industrial-maintenance distributor, with Newark, Columbus, and Reno warehouses, 32 SKUs, and six suppliers. All records are synthetic. January 2024–August 2026; USD.

## Open the report
Open `Northline.pbip` in Power BI Desktop. If this repository is moved, change the `DataFolder` Power Query parameter to its `data/csv/` folder, including the trailing slash, then refresh. The repository excludes cached model data and credentials.

The five pages share six monthly KPI cards, a slicer row, twelve-month trends and operational detail tables:
- **Operations Overview:** shipment volume, order service levels, backlog, stock investment and shipment cycle time.
- **Inventory Health:** stock aging, stockout exposure, rolling turnover and demand coverage.
- **Order Fulfillment:** due-month service levels, historical backlogs and overdue units by stage.
- **Supplier Performance:** quantity-weighted receipt lead times and purchase-order delivery reliability.
- **Warehouse Throughput:** stage capacity, completed unit tasks, waiting time and queues.

## Metric definitions
- **OTIF / On Time In Full:** orders shipped in full by their promised ship date divided by orders due in the selected month. This measures warehouse dispatch service, not customer delivery. Every order has one SKU and one warehouse. No cancellations are simulated.
- **Due Month Fill Rate:** units on orders due that month shipped by that month's end, divided by all units due. This differs from immediate stock availability or first-shipment fill rate. Shipment volume is measured by actual dispatch date.
- **Backlog:** remaining unshipped units at month-end, including Pick, Pack and Dispatch queues. Overdue means the promised ship date is earlier than the snapshot date. Order counts are distinct even when partial quantities occupy different stages.
- **Inventory:** owned storage plus picked/packed units until dispatch. Fixed standard cost by SKU; no currency translation, write-offs, returns, damage or inter-warehouse transfers. Opening + receipts − shipments = closing. FIFO stock aging uses receipt dates for stored lots. Picked/packed stock is separately valued and excluded from stored-stock aging buckets; aged share uses total owned inventory value as denominator.
- **Turnover 12M:** trailing twelve-month shipment COGS divided by daily-weighted average owned inventory at cost. Blank until twelve full months exist. It is a trailing-period ratio, not the sum of monthly ratios.
- **90d cover days:** month-end owned units divided by average daily shipments over the last 90 calendar days. Blank without 90 days or demand; coverage based on unfulfilled demand may differ.
- **Stockout SKU-days:** warehouse/SKU working days with zero storage stock at day-end; picked stock is not available to new orders. It is exposure, not a count of lost sales.
- **Supplier OTIF:** full POs received by promised date divided by POs due that month, including late/unreceived POs. Receipt lead time uses receipt-date cohorts and is quantity-weighted. POs have one complete receipt; customer shipments may be partial.
- **Stage completions/capacity:** unit tasks at Pick, Pack and Dispatch. All-stage totals count distinct processing steps, not unique physical shipped units. Capacity use is not an efficiency or labor-productivity score. Stage wait is weighted by units completed, not an average of unweighted task averages. Queue/capacity days compares month-end queued tasks with average daily capacity on working days.

## Simulation and known scope
The deterministic seed is 20260922. Demand increases modestly over time and peaks in October–November. Imported motion parts encounter extra supplier delays in late 2025. Columbus packing capacity is constrained October 2025–February 2026 and increased from March 2026. Some SKUs lose demand from April 2025, producing aged stock. Reordering uses forecast demand, contractual lead time and coverage buffers. These scenarios illustrate investigation; they do not establish actual business losses or causal benefits.

Warehouse processing uses weekdays, not a holiday calendar. Downstream stages process before upstream each day, avoiding same-day passage through every step. Work in progress and unpicked queues carry forward. All observations stop at August 31, 2026: future receipts and shipment dates remain blank.

Shared Warehouse and Product dimensions filter the operational facts; Supplier filters Product. Stage filters throughput and backlog. Facts have no fact-to-fact relationships, avoiding duplicate aggregation. The reporting month and trend month dimensions are disconnected and DAX applies their periods explicitly. Throughput has no SKU/product filter because available stage capacity has no product allocation.

## Reproduce and validate
Run `python data/generate.py`, `python data/validate.py`, then `python scripts/build_report.py`. Close Power BI before rebuilding; the builder replaces the report layout and model definitions. All required templates are included. Source CSVs, definitions and report design are versioned; refresh brings the CSVs into Power BI. Source checks reconcile all 32 months, partial shipments, FIFO stored-stock valuation and historical backlog.

Raw grains: Orders one sales order; Shipments one partial dispatch; Purchases one PO; Receipts one PO receipt; Inventory one warehouse/SKU/month-end with daily value sums; Backlog one queued task/month-end; Throughput one warehouse/stage/working day. Supporting dimensions are Warehouses, Products, Suppliers and Stages.

## Suggested review path
Start with Operations Overview, then select Columbus DC and compare September 2025, February 2026 and August 2026. Its queued units rise from 441 to 6,978, then fall to 1,759 after packing capacity increases. Use Warehouse Throughput to see how work moves between the packing and dispatch queues: removing one constraint does not eliminate the entire backlog. Order Fulfillment shows the corresponding service impact.

Use Supplier Performance to compare imported and domestic lead times, and Inventory Health to distinguish available stored stock, picked/packed inventory, aging and stockout exposure. Low aggregate aging does not mean every SKU has adequate availability.

## Validation evidence
The source validation passes inventory continuity, shipment quantities, FIFO aging valuation, historical backlog and capacity constraints. Live model validation compared 1,632 DAX results against independent CSV aggregations across 32 months and three warehouses. All 215 measures compiled successfully. `scripts/export_model_checks.ps1` exports a live Desktop model for `data/validate_model.py`; it accepts the local Analysis Services port and output file. Its TOM/ADOMD dependency paths reflect the author's development environment and may need adjusting on another machine.
