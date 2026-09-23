"""Deterministic operational simulation. All entities and transactions are synthetic."""
import csv, random, math, calendar, json
from collections import defaultdict, deque
from datetime import date, timedelta
from pathlib import Path
R=Path(__file__).resolve().parent; OUT=R/'csv';OUT.mkdir(exist_ok=True)
rng=random.Random(20260922)
START=date(2024,1,1);END=date(2026,8,31)
def work(d):return d.weekday()<5
def nextwork(d):
 while not work(d):d+=timedelta(days=1)
 return d
def save(n,rows):
 with (OUT/(n+'.csv')).open('w',newline='',encoding='utf-8') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
warehouses=[dict(WarehouseID=i+1,Warehouse=n,Region=r) for i,(n,r) in enumerate([('Newark DC','East'),('Columbus DC','Central'),('Reno DC','West')])]
suppliers=[dict(SupplierID=i+1,Supplier=n,Origin=o,ContractLeadDays=l) for i,(n,o,l) in enumerate([('Atlas Components','USA',7),('Crestline Industrial','USA',10),('Harbor Fasteners','Mexico',16),('Summit Safety','USA',9),('Pacific Motion','Taiwan',30),('Evergreen Packaging','USA',8)])]
products=[]
categories=['Fasteners','Safety Equipment','Motion Components','Packaging']
for i in range(32):
 cat=categories[i//8];sup=[3,4,5,6][i//8] if i%3 else 1+i%2
 products.append(dict(ProductID=i+1,SKU=f'NL-{1001+i}',Product=f'{cat} {i%8+1:02}',Category=cat,SupplierID=sup,UnitCostUSD=round(rng.uniform(5,85),2),DemandClass='Slow moving' if i%8==7 else 'Core'))
P={p['ProductID']:p for p in products};S={s['SupplierID']:s for s in suppliers}
lots={};inv={};initial={};po=[];due=defaultdict(list);orders=[];shipments=[];receipts=[];backlog=[];inventory=[];throughput=[];ledger=[]
queues={w['WarehouseID']:{s:deque() for s in ['Pick','Pack','Dispatch']} for w in warehouses}
daily_values=defaultdict(float);stockout=defaultdict(int);month_receipts=defaultdict(int);month_ships=defaultdict(int)
for w in warehouses:
 for p in products:
  k=(w['WarehouseID'],p['ProductID']);qty=rng.randint(140,270) if p['DemandClass']=='Core' else rng.randint(100,170)
  lots[k]=deque([[START-timedelta(days=rng.randint(5,100)),qty]]);inv[k]=qty;initial[k]=qty
oid=0;sid=0;pid=0
for di in range((END-START).days+1):
 d=START+timedelta(days=di);ym=d.year*100+d.month
 # Goods receipts are full purchase-order receipts. Events beyond END stay unobserved.
 for purchase in due[d]:
  k=(purchase['WarehouseID'],purchase['ProductID']);qty=purchase['OrderedUnits'];inv[k]+=qty;lots[k].append([d,qty]);month_receipts[k]+=qty
  purchase['ReceiptDate']=d;purchase['ReceivedUnits']=qty
  receipts.append(dict(ReceiptID=len(receipts)+1,PurchaseID=purchase['PurchaseID'],Date=d,WarehouseID=k[0],ProductID=k[1],SupplierID=purchase['SupplierID'],Units=qty,ValueUSD=round(qty*P[k[1]]['UnitCostUSD'],2),LeadDays=(d-purchase['OrderDate']).days,OnTime=int(d<=purchase['PromisedDate'])))
 if work(d):
  for w in warehouses:
   wid=w['WarehouseID'];q=queues[wid]
   seasonal=1.25 if d.month in [10,11] else 1.0
   for j in range(round(rng.uniform(10,15)*seasonal*(1+di/4500))):
    p=rng.choices(products,weights=[.15 if x['DemandClass']=='Slow moving' and d>=date(2025,4,1) else 1 for x in products])[0]
    units=rng.randint(3,22);oid+=1
    o=dict(OrderID=oid,OrderDate=d,PromisedDate=nextwork(d+timedelta(days=3 if rng.random()<.7 else 5)),WarehouseID=wid,ProductID=p['ProductID'],Priority='Expedite' if rng.random()<.15 else 'Standard',OrderedUnits=units,ShippedUnits=0,CompleteDate='',UnitPriceUSD=round(p['UnitCostUSD']*1.55,2))
    orders.append(o);q['Pick'].append(dict(order=o,qty=units,entered=d))
   # Process downstream first: no instantaneous passage through all warehouse stages.
   for stage,base in [('Dispatch',235),('Pack',215),('Pick',240)]:
    capacity=round(base*rng.uniform(.85,1.12))
    if wid==2 and stage=='Pack' and date(2025,10,1)<=d<=date(2026,2,28):capacity=135
    if wid==2 and stage=='Pack' and d>=date(2026,3,1):capacity=255
    opening=sum(x['qty'] for x in q[stage]);budget=capacity;processed=0;waitunits=0;count=len(q[stage])
    for _ in range(count):
     task=q[stage].popleft();o=task['order'];k=(wid,o['ProductID']);available=inv[k] if stage=='Pick' else task['qty'];take=min(task['qty'],budget,available)
     if take:
      budget-=take;processed+=take;waitunits+=take*(d-task['entered']).days
      if stage=='Pick':
       inv[k]-=take;left=take
       while left:
        use=min(left,lots[k][0][1]);lots[k][0][1]-=use;left-=use
        if not lots[k][0][1]:lots[k].popleft()
       q['Pack'].append(dict(order=o,qty=take,entered=d))
      elif stage=='Pack':q['Dispatch'].append(dict(order=o,qty=take,entered=d))
      else:
       sid+=1;o['ShippedUnits']+=take;month_ships[k]+=take
       if o['ShippedUnits']==o['OrderedUnits']:o['CompleteDate']=d
       shipments.append(dict(ShipmentID=sid,OrderID=o['OrderID'],Date=d,WarehouseID=wid,ProductID=o['ProductID'],Units=take,COGSUSD=round(take*P[o['ProductID']]['UnitCostUSD'],2),RevenueUSD=round(take*o['UnitPriceUSD'],2),CycleUnitDays=take*(d-o['OrderDate']).days,OnTimeUnits=take if d<=o['PromisedDate'] else 0))
     task['qty']-=take
     if task['qty']:q[stage].append(task)
    throughput.append(dict(Date=d,WarehouseID=wid,Stage=stage,CapacityUnits=capacity,CompletedUnits=processed,OpeningQueueUnits=opening,ClosingQueueUnits=sum(x['qty'] for x in q[stage]),WaitUnitDays=waitunits))
  # Reorder policy based on baseline demand and supplier lead time, with occasional overbuy.
  for w in warehouses:
   for p in products:
    k=(w['WarehouseID'],p['ProductID']);s=S[p['SupplierID']];onorder=sum(x['OrderedUnits'] for x in po if (x['WarehouseID'],x['ProductID'])==k and not x['ReceiptDate'])
    daily=5.2 if p['DemandClass']=='Core' else (1.1 if d>=date(2025,4,1) else 4.5)
    if inv[k]+onorder<daily*(s['ContractLeadDays']+8):
     qty=round(daily*(s['ContractLeadDays']+35)-inv[k]-onorder);pid+=1
     promised=nextwork(d+timedelta(days=s['ContractLeadDays']))
     delay=rng.choices([0,2,5,12],[.66,.16,.12,.06])[0]
     if s['SupplierID']==5 and date(2025,8,1)<=d<=date(2025,12,31):delay+=rng.randint(8,20)
     actual=nextwork(promised+timedelta(days=delay))
     purchase=dict(PurchaseID=pid,OrderDate=d,PromisedDate=promised,WarehouseID=k[0],ProductID=k[1],SupplierID=s['SupplierID'],OrderedUnits=qty,ReceivedUnits=0,ReceiptDate='')
     po.append(purchase);due[actual].append(purchase)
 # Inventory ownership includes picked/packed goods until dispatch; aging follows original lots
 # separately from floor stock. WIP uses source cost, aged stock applies only storage lots.
 for k in inv:
  wip=sum(t['qty'] for stage in ['Pack','Dispatch'] for t in queues[k[0]][stage] if t['order']['ProductID']==k[1])
  daily_values[k]+=(inv[k]+wip)*P[k[1]]['UnitCostUSD']
  if work(d) and inv[k]==0:stockout[k]+=1
 if d.day==calendar.monthrange(d.year,d.month)[1]:
  for k in inv:
   wip=sum(t['qty'] for stage in ['Pack','Dispatch'] for t in queues[k[0]][stage] if t['order']['ProductID']==k[1]);closing=inv[k]+wip;cost=P[k[1]]['UnitCostUSD']
   age=[sum(qty for rec,qty in lots[k] if lo<=(d-rec).days<=hi) for lo,hi in [(0,30),(31,60),(61,90),(91,180),(181,10000)]]
   row=dict(Date=d,WarehouseID=k[0],ProductID=k[1],OpeningUnits=initial[k],ReceivedUnits=month_receipts[k],ShippedUnits=month_ships[k],StorageUnits=inv[k],WIPUnits=wip,ClosingUnits=closing,ClosingValueUSD=round(closing*cost,2),DailyValueSumUSD=round(daily_values[k],2),CalendarDays=d.day,StockoutDays=stockout[k])
   for bucket,qty in zip(['0to30','31to60','61to90','91to180','Over180'],age):row['Age'+bucket+'USD']=round(qty*cost,2)
   inventory.append(row);assert initial[k]+month_receipts[k]-month_ships[k]==closing
   initial[k]=closing
  for wid,q in queues.items():
   for stage,tasks in q.items():
    for t in tasks:
     o=t['order'];backlog.append(dict(Date=d,OrderID=o['OrderID'],WarehouseID=wid,ProductID=o['ProductID'],Stage=stage,OpenUnits=t['qty'],OpenValueUSD=round(t['qty']*o['UnitPriceUSD'],2),OverdueUnits=t['qty'] if o['PromisedDate']<d else 0,AgeUnitDays=(d-o['OrderDate']).days*t['qty']))
  daily_values.clear();stockout.clear();month_receipts.clear();month_ships.clear()
byorder=defaultdict(list)
for s in shipments:byorder[s['OrderID']].append(s)
for o in orders:
 cutoff=o['PromisedDate'].replace(day=calendar.monthrange(o['PromisedDate'].year,o['PromisedDate'].month)[1])
 o['FulfilledByDueMonthUnits']=sum(s['Units'] for s in byorder[o['OrderID']] if s['Date']<=cutoff)
 o['OnTimeFull']=int(bool(o['CompleteDate']) and o['CompleteDate']<=o['PromisedDate'])
for o in po:o['OnTimeFull']=int(bool(o['ReceiptDate']) and o['ReceiptDate']<=o['PromisedDate'])
for n,rows in [('Warehouses',warehouses),('Suppliers',suppliers),('Products',products),('Orders',orders),('Shipments',shipments),('Purchases',po),('Receipts',receipts),('Inventory',inventory),('Backlog',backlog),('Throughput',throughput)]:save(n,rows)
print(json.dumps({n:len(rows) for n,rows in [('Orders',orders),('Shipments',shipments),('Purchases',po),('Receipts',receipts),('Inventory',inventory),('Backlog',backlog),('Throughput',throughput)]}))
