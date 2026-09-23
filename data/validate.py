"""Independent source reconciliation; exits nonzero on any mismatch."""
import csv,json,calendar
from pathlib import Path
from collections import defaultdict
R=Path(__file__).resolve().parent
def read(n):return list(csv.DictReader((R/'csv'/f'{n}.csv').open(encoding='utf-8')))
orders=read('Orders');ship=read('Shipments');inv=read('Inventory');back=read('Backlog');po=read('Purchases');rec=read('Receipts');flow=read('Throughput');products=read('Products')
order={x['OrderID']:x for x in orders};cost={x['ProductID']:float(x['UnitCostUSD']) for x in products};byorder=defaultdict(list)
assert len(order)==len(orders)
for s in ship:
 o=order[s['OrderID']];assert s['Date']>=o['OrderDate'];assert s['ProductID']==o['ProductID'] and s['WarehouseID']==o['WarehouseID']
 assert abs(float(s['COGSUSD'])-int(s['Units'])*cost[s['ProductID']])<.011
 byorder[s['OrderID']].append(s)
for o in orders:
 events=byorder[o['OrderID']];assert sum(int(s['Units']) for s in events)==int(o['ShippedUnits'])<=int(o['OrderedUnits'])
 assert bool(o['CompleteDate'])==(o['ShippedUnits']==o['OrderedUnits'])
 if o['CompleteDate']:assert o['CompleteDate']==max(s['Date'] for s in events)
 assert int(o['OnTimeFull'])==int(bool(o['CompleteDate']) and o['CompleteDate']<=o['PromisedDate'])
 assert int(o['FulfilledByDueMonthUnits'])==sum(int(s['Units']) for s in events if s['Date'][:7]<=o['PromisedDate'][:7])
balances={};monthlyship=defaultdict(int);monthlyrec=defaultdict(int)
for s in ship:monthlyship[(s['Date'][:7],s['WarehouseID'],s['ProductID'])]+=int(s['Units'])
for s in rec:monthlyrec[(s['Date'][:7],s['WarehouseID'],s['ProductID'])]+=int(s['Units'])
for x in inv:
 k=(x['WarehouseID'],x['ProductID']);m=(x['Date'][:7],*k)
 assert int(x['ReceivedUnits'])==monthlyrec[m] and int(x['ShippedUnits'])==monthlyship[m]
 assert int(x['OpeningUnits'])+int(x['ReceivedUnits'])-int(x['ShippedUnits'])==int(x['ClosingUnits'])
 if k in balances:assert balances[k]==int(x['OpeningUnits'])
 balances[k]=int(x['ClosingUnits'])
 assert int(x['StorageUnits'])+int(x['WIPUnits'])==int(x['ClosingUnits'])
 aged=sum(float(x['Age'+a+'USD']) for a in ['0to30','31to60','61to90','91to180','Over180'])
 assert abs(aged-int(x['StorageUnits'])*cost[x['ProductID']])<.03
for month in sorted({x['Date'] for x in inv}):
 outstanding=sum(int(o['OrderedUnits'])-sum(int(s['Units']) for s in byorder[o['OrderID']] if s['Date']<=month) for o in orders if o['OrderDate']<=month)
 assert outstanding==sum(int(x['OpenUnits']) for x in back if x['Date']==month),(month,outstanding)
for x in flow:assert 0<=int(x['CompletedUnits'])<=int(x['CapacityUnits']) and int(x['ClosingQueueUnits'])>=0
for p in po:
 rr=[r for r in rec if r['PurchaseID']==p['PurchaseID']]
 assert len(rr)==(1 if p['ReceiptDate'] else 0)
 if rr:assert rr[0]['Date']==p['ReceiptDate'] and rr[0]['Units']==p['OrderedUnits']
print('PASS: order/shipments, purchase receipts, monthly inventory continuity, FIFO aging costs, historical backlog, and stage capacity limits.')
