"""Compare live DAX monthly warehouse results with independent CSV aggregations."""
import csv,json,sys,math
from pathlib import Path
from collections import defaultdict
root=Path(__file__).resolve().parents[1]
def load(name):return list(csv.DictReader((root/'data/csv'/f'{name}.csv').open(encoding='utf-8')))
def group(name,date):
 out=defaultdict(list)
 for r in load(name):out[(int(r[date][:7].replace('-','')),int(r['WarehouseID']))].append(r)
 return out
ship=group('Shipments','Date');stock=group('Inventory','Date');back=group('Backlog','Date')
orders=group('Orders','PromisedDate');receipts=group('Receipts','Date');po=group('Purchases','PromisedDate');stage=group('Throughput','Date')
def total(rows,col):return sum(float(r[col]) for r in rows)
def ratio(a,b):return a/b if b else None
checks=0
for row in json.loads(Path(sys.argv[1]).read_text(encoding='utf-8-sig')):
 key=(row['YearMonth'],row['WarehouseID']);s=ship[key];i=stock[key];b=back[key];o=orders[key];r=receipts[key];p=po[key];t=stage[key]
 previous=(key[0]-1 if key[0]%100>1 else key[0]-89,key[1])
 expected={
 'ShippedUnits':total(s,'Units'),'InventoryValue':total(i,'ClosingValueUSD'),
 'BacklogUnits':total(b,'OpenUnits'),'OverdueUnits':total(b,'OverdueUnits'),
 'DueOrders':len(o),'DueUnits':total(o,'OrderedUnits'),
 'Fill':ratio(total(o,'FulfilledByDueMonthUnits'),total(o,'OrderedUnits')),
 'OTIF':ratio(total(o,'OnTimeFull'),len(o)),
 'Cycle':ratio(total(s,'CycleUnitDays'),total(s,'Units')),
 'ReceivedUnits':total(r,'Units') if r else None,
 'Lead':ratio(sum(float(x['LeadDays'])*int(x['Units']) for x in r),total(r,'Units')),
 'SupplierOTIF':ratio(total(p,'OnTimeFull'),len(p)),
 'Capacity':total(t,'CapacityUnits'),'Completed':total(t,'CompletedUnits'),
 'Wait':ratio(total(t,'WaitUnitDays'),total(t,'CompletedUnits')),
 'Aged90':total(i,'Age91to180USD')+total(i,'AgeOver180USD'),
 'PreviousShipped':total(ship[previous],'Units') if previous[0]>=202401 else None}
 for field,want in expected.items():
  got=row[field]
  assert (got is None and want is None) or (got is not None and want is not None and math.isclose(got,want,abs_tol=0.001,rel_tol=1e-8)),(key,field,got,want)
  checks+=1
assert checks==32*3*17,checks
print(f'PASS: {checks:,} live DAX values match CSV calculations across all 32 months and three warehouses.')
