"""Build a portable PBIP/TMDL report from validated synthetic CSVs."""
import ast,json,copy,re,uuid,csv,shutil
from pathlib import Path
R=Path(__file__).resolve().parents[1]
SOURCE=R.parent/'asterworks-revenue-analytics'
M=R/'Northline.SemanticModel/definition';M.mkdir(parents=True,exist_ok=True);(M/'tables').mkdir(exist_ok=True)
RR=R/'Northline.Report';RR.mkdir(exist_ok=True)
RES=RR/'StaticResources/RegisteredResources';RES.mkdir(parents=True,exist_ok=True)
def dump(p,o):p.write_text(json.dumps(o,indent=2),encoding='utf-8')
# Pure visual constructors are copied once to keep this repository self-contained.
helpers=R/'scripts/visual_helpers.py'
if not helpers.exists():
 tree=ast.parse((SOURCE/'scripts/build_executive.py').read_text(encoding='utf-8-sig'))
 helpers.write_text('import json,uuid\n'+ '\n\n'.join(ast.unparse(n) for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ['lit','color','measure','column','props','visual','bind','finish','chart']),encoding='utf-8')
exec(compile(helpers.read_text(encoding='utf-8'),str(helpers),'exec'))
templatefile=R/'scripts/kpi-template.json'
if not templatefile.exists():shutil.copy2(SOURCE/'scripts/kpi-template.json',templatefile)
template=json.loads(templatefile.read_text(encoding='utf-8-sig'))
themefile=R/'branding/Northline_Theme.json';themefile.parent.mkdir(exist_ok=True)
if not themefile.exists():
 theme=json.loads((SOURCE/'branding/AsterWorks_Light_Theme.json').read_text(encoding='utf-8-sig'));theme['name']='Northline Operations';theme['dataColors']=['#267B93','#ED9B40','#5576B9','#65AA94','#B36B77','#8E82B8','#89A9B0','#C6AA73'];theme['tableAccent']='#267B93';theme['backgroundLight']='#F0F4F8'
 dump(themefile,theme)
shutil.copy2(themefile,RES/themefile.name)
dump(R/'Northline.pbip',{'version':'1.0','artifacts':[{'report':{'path':'Northline.Report'}}],'settings':{'enableAutoRecovery':True}})
dump(RR/'definition.pbir',{'version':'4.0','datasetReference':{'byPath':{'path':'../Northline.SemanticModel'}}})
dump(R/'Northline.SemanticModel/definition.pbism',{'version':'4.2','settings':{'qnaEnabled':False}})
(M/'database.tmdl').write_text('database\n\tcompatibilityLevel: 1606\n',encoding='utf-8')
(M/'expressions.tmdl').write_text(f'expression DataFolder = "{(R/"data/csv").as_posix()}/" meta [IsParameterQuery=true, Type="Text", IsParameterQueryRequired=true]\n\tannotation PBI_ResultType = Text\n',encoding='utf-8')
tables=[];numeric={};dates={}
for path in sorted((R/'data/csv').glob('*.csv')):
 name=path.stem;tables.append(name)
 rows=list(csv.DictReader(path.open(encoding='utf-8')));cols=list(rows[0]);types={}
 for col in cols:
  vals=[r[col] for r in rows if r[col]]
  if col.endswith('Date') or col=='Date':typ='dateTime';mt='type date';fmt='yyyy-MM-dd'
  elif all(re.fullmatch(r'-?\d+(\.\d+)?',x) for x in vals):typ='decimal' if any('.' in x for x in vals) else 'int64';mt='Currency.Type' if typ=='decimal' else 'Int64.Type';fmt='$#,0.00' if 'USD' in col else '#,0'
  else:typ='string';mt='type text';fmt=None
  types[col]=(typ,mt,fmt)
 s=f'table {name}\n'
 for col,(typ,mt,fmt) in types.items():
  s+=f'\n\tcolumn {col}\n\t\tdataType: {typ}\n\t\tsourceColumn: {col}\n\t\tsummarizeBy: none\n'
  if fmt:s+=f'\t\tformatString: {fmt}\n'
 s+=f'\n\tpartition {name} = m\n\t\tmode: import\n\t\tsource =\n\t\t\tlet\n\t\t\t Source = Csv.Document(File.Contents(DataFolder & "{name}.csv"), [Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.Csv]),\n\t\t\t Headers = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),\n\t\t\t Nulls = Table.ReplaceValue(Headers, "", null, Replacer.ReplaceValue, Table.ColumnNames(Headers)),\n\t\t\t Typed = Table.TransformColumnTypes(Nulls, {{'+', '.join('{"'+col+'", '+mt+'}' for col,(typ,mt,fmt) in types.items())+'}, "en-US")\n\t\t\tin Typed\n'
 (M/f'tables/{name}.tmdl').write_text(s,encoding='utf-8')
for name in ['Calendar','Reporting Month','Trend Month']:
 src=R/f'scripts/date-templates/{name}.tmdl'
 # These self-contained date dimensions use the same 2024-2026 reporting window.
 shutil.copy2(src,M/f'tables/{name}.tmdl');tables.append(name)
(M/'tables/Stages.tmdl').write_text('table Stages\n\tcolumn Stage\n\t\tdataType: string\n\t\tsourceColumn: Stage\n\t\tsortByColumn: StageOrder\n\tcolumn StageOrder\n\t\tdataType: int64\n\t\tsourceColumn: StageOrder\n\tpartition Stages = m\n\t\tmode: import\n\t\tsource = #table(type table [Stage=text,StageOrder=Int64.Type], {{"Pick",1},{"Pack",2},{"Dispatch",3}})\n',encoding='utf-8');tables.append('Stages')
rels=[]
def rel(t,c,to,tc,active=True):rels.append(f'relationship {uuid.uuid4()}\n\tfromColumn: {t}.{c}\n\ttoColumn: {to}.{tc}\n'+('' if active else '\tisActive: false\n'))
rel('Products','SupplierID','Suppliers','SupplierID')
for t in ['Orders','Shipments','Purchases','Receipts','Inventory','Backlog','Throughput']:
 rel(t,'WarehouseID','Warehouses','WarehouseID')
 if t!='Throughput':rel(t,'ProductID','Products','ProductID')
 datecol='PromisedDate' if t in ['Orders','Purchases'] else 'Date'
 rel(t,datecol,'Calendar','Date')
 if t in ['Orders','Purchases']:rel(t,'OrderDate','Calendar','Date',False)
for t in ['Backlog','Throughput']:rel(t,'Stage','Stages','Stage')
(M/'relationships.tmdl').write_text('\n'.join(rels),encoding='utf-8')
tables.append('Metrics')
query_order=['DataFolder']+tables
(M/'model.tmdl').write_text('model Model\n\tculture: en-US\n\tdefaultPowerBIDataSourceVersion: powerBI_V3\n\tsourceQueryCulture: en-US\n\tdataAccessOptions\n\t\tlegacyRedirects\n\t\treturnErrorValuesAsNull\n\nannotation __PBI_TimeIntelligenceEnabled = 0\n\nannotation PBI_QueryOrder = '+json.dumps(query_order)+'\n\n'+ '\n'.join("ref table '"+t+"'" for t in tables)+'\n',encoding='utf-8')
measures={};money='$#,0;($#,0);$0'
def add(n,expr,fmt='#,0',lower=False):measures[n]=(expr,fmt,lower)
add('Selected Month',"SELECTEDVALUE ( 'Reporting Month'[MonthStart], MAX ( 'Reporting Month'[MonthStart] ) )",'yyyy-MM-dd')
bases={
 'Shipped Units':('SUM ( Shipments[Units] )','#,0',False),
 'Shipment COGS':('SUM ( Shipments[COGSUSD] )',money,False),
 'Due Orders':('COUNTROWS ( Orders )','#,0',False),
 'Due Units':('SUM ( Orders[OrderedUnits] )','#,0',False),
 'Due Month Fill Rate':('DIVIDE ( SUM ( Orders[FulfilledByDueMonthUnits] ), SUM ( Orders[OrderedUnits] ) )','0.0%',False),
 'On Time In Full':('DIVIDE ( SUM ( Orders[OnTimeFull] ), COUNTROWS ( Orders ) )','0.0%',False),
 'Ship Cycle Days':('DIVIDE ( SUM ( Shipments[CycleUnitDays] ), SUM ( Shipments[Units] ) )','0.0',True),
 'Backlog Units':('COALESCE ( SUM ( Backlog[OpenUnits] ), 0 )','#,0',True),
 'Backlog Value':('COALESCE ( SUM ( Backlog[OpenValueUSD] ), 0 )',money,True),
 'Backlog Orders':('COALESCE ( DISTINCTCOUNT ( Backlog[OrderID] ), 0 )','#,0',True),
 'Overdue Units':('COALESCE ( SUM ( Backlog[OverdueUnits] ), 0 )','#,0',True),
 'Backlog Age':('DIVIDE ( SUM ( Backlog[AgeUnitDays] ), SUM ( Backlog[OpenUnits] ) )','0.0',True),
 'Inventory Value':('SUM ( Inventory[ClosingValueUSD] )',money,True),
 'Inventory Units':('SUM ( Inventory[ClosingUnits] )','#,0',False),
 'Aged 90 Value':('SUM ( Inventory[Age91to180USD] ) + SUM ( Inventory[AgeOver180USD] )',money,True),
 'Aged 180 Value':('SUM ( Inventory[AgeOver180USD] )',money,True),
 'Aged 90 Share':('DIVIDE ( [Aged 90 Value Base], [Inventory Value Base] )','0.0%',True),
 'Stockout SKU Days':('SUM ( Inventory[StockoutDays] )','#,0',True),
 'Storage Value':('SUMX ( Inventory, Inventory[ClosingValueUSD] * DIVIDE ( Inventory[StorageUnits], Inventory[ClosingUnits] ) )',money,False),
 'WIP Value':('SUMX ( Inventory, Inventory[ClosingValueUSD] * DIVIDE ( Inventory[WIPUnits], Inventory[ClosingUnits] ) )',money,True),
 'Received Units':('SUM ( Receipts[Units] )','#,0',False),
 'Receipt Value':('SUM ( Receipts[ValueUSD] )',money,False),
 'Receipt Lead Days':('DIVIDE ( SUMX ( Receipts, Receipts[LeadDays] * Receipts[Units] ), SUM ( Receipts[Units] ) )','0.0',True),
 'Due Purchase Orders':('COUNTROWS ( Purchases )','#,0',False),
 'Supplier OTIF':('DIVIDE ( SUM ( Purchases[OnTimeFull] ), COUNTROWS ( Purchases ) )','0.0%',False),
 'Late Purchase Orders':('COUNTROWS ( Purchases ) - SUM ( Purchases[OnTimeFull] )','#,0',True),
 'Stage Completions':('SUM ( Throughput[CompletedUnits] )','#,0',False),
 'Stage Capacity':('SUM ( Throughput[CapacityUnits] )','#,0',False),
 'Capacity Use':('DIVIDE ( [Stage Completions Base], [Stage Capacity Base] )','0.0%',False),
 'Stage Wait Days':('DIVIDE ( SUM ( Throughput[WaitUnitDays] ), SUM ( Throughput[CompletedUnits] ) )','0.0',True),
}
for bucket in ['0to30','31to60','61to90','91to180','Over180']:bases['Age '+bucket]=('SUM ( Inventory[Age'+bucket+'USD] )',money,False)
for n,(expr,fmt,lower) in bases.items():
 add(n+' Base',expr,fmt,lower)
 for suffix,dt in [('', '[Selected Month]'),(' Previous','EDATE ( [Selected Month], -1 )'),(' Trend',"SELECTEDVALUE ( 'Trend Month'[MonthStart] )")]:
  guard='D >= DATE ( 2024, 1, 1 )'
  if suffix==' Trend':guard='NOT ISBLANK ( D ) && D >= EDATE ( [Selected Month], -11 ) && D <= [Selected Month]'
  add(n+suffix,f'VAR D = {dt}\nRETURN IF ( {guard}, CALCULATE ( [{n} Base], REMOVEFILTERS ( Calendar ), DATESBETWEEN ( Calendar[Date], D, EOMONTH ( D, 0 ) ) ) )',fmt,lower)
 change=f'FORMAT ( ( [{n}] - P ) * 100, "+0.0;-0.0;0.0" ) & " pp"' if fmt=='0.0%' else f'IF ( P = 0, "N/A", FORMAT ( DIVIDE ( [{n}] - P, P ), "+0.0%;-0.0%;0.0%" ) )'
 add(n+' Change',f'VAR P = [{n} Previous]\nRETURN IF ( ISBLANK ( P ) || ISBLANK ( [{n}] ), "N/A", {change} )','')
 sign='-' if lower else ''
 add(n+' Color',f'VAR P = [{n} Previous]\nVAR Delta = {sign}( [{n}] - P )\nRETURN SWITCH ( TRUE (), ISBLANK ( P ) || ISBLANK ( [{n}] ), "#000000", Delta > 0.000001, "#237A42", Delta < -0.000001, "#B3261E", "#000000" )','')
add('Turnover 12M', 'VAR S = [Selected Month] VAR B = EDATE ( S, -11 ) VAR E = EOMONTH ( S, 0 ) VAR C = CALCULATE ( SUM ( Shipments[COGSUSD] ), REMOVEFILTERS ( Calendar ), DATESBETWEEN ( Calendar[Date], B, E ) ) VAR V = CALCULATE ( SUM ( Inventory[DailyValueSumUSD] ), REMOVEFILTERS ( Calendar ), DATESBETWEEN ( Calendar[Date], B, E ) ) RETURN IF ( B >= DATE ( 2024, 1, 1 ), DIVIDE ( C, DIVIDE ( V, DATEDIFF ( B, E, DAY ) + 1 ) ) )','0.0"x"')
add('Days Cover','VAR E = EOMONTH ( [Selected Month], 0 ) VAR B = E - 89 VAR U = CALCULATE ( SUM ( Shipments[Units] ), REMOVEFILTERS ( Calendar ), DATESBETWEEN ( Calendar[Date], B, E ) ) RETURN IF ( B >= DATE ( 2024, 1, 1 ), DIVIDE ( [Inventory Units], DIVIDE ( U, 90 ) ) )','0.0')
add('Queue Capacity Days','DIVIDE ( [Backlog Units], DIVIDE ( [Stage Capacity], CALCULATE ( DISTINCTCOUNT ( Throughput[Date] ), REMOVEFILTERS ( Calendar ), DATESBETWEEN ( Calendar[Date], [Selected Month], EOMONTH ( [Selected Month], 0 ) ) ) ) )','0.0')
add('Report Heading','FORMAT ( [Selected Month], "MMMM yyyy" ) & " | Operations & Inventory | USD"','')
s='table Metrics\n\tcolumn Placeholder\n\t\tdataType: int64\n\t\tisHidden\n\t\tsourceColumn: Placeholder\n\tpartition Metrics = m\n\t\tmode: import\n\t\tsource = #table(type table [Placeholder=Int64.Type], {{1}})\n'
for n,(expr,fmt,lower) in measures.items():s+=f"\n\tmeasure '{n}' =\n"+'\n'.join('\t\t\t'+l for l in expr.splitlines())+f'\n\t\tformatString: {fmt or chr(34)+chr(34)}\n\t\tdisplayFolder: '+('Supporting' if n.endswith(('Base','Previous','Trend','Change','Color')) else 'Performance')+'\n'
(M/'tables/Metrics.tmdl').write_text(s,encoding='utf-8')
report={'config':json.dumps({'version':'5.75','themeCollection':{'customTheme':{'name':themefile.name,'type':1,'version':{'visual':'2.12.0','report':'3.4.0','page':'2.3.1'}}},'activeSectionIndex':0,'landingPageName':'OperationsOverview'}),'layoutOptimization':0,'resourcePackages':[{'resourcePackage':{'name':'RegisteredResources','type':1,'items':[{'name':themefile.name,'path':themefile.name,'type':201}]}}],'sections':[],'theme':themefile.name}
def textbox(text,x,y,w,h,size=20,bold=False,col='#152B45',align='left'):
 v,c,s=visual('textbox',x,y,w,h);s['objects']={'general':[{'properties':{'paragraphs':[{'textRuns':[{'value':text,'textStyle':{'fontFamily':'Arial','fontSize':f'{size}pt','fontWeight':'bold' if bold else 'normal','color':col}}],'horizontalTextAlignment':align}]}}]};s['vcObjects']={'background':props(show=lit('false')),'border':props(show=lit('false'))};finish(v,c)
def start(title,kpis,slicers):
 global page
 page={'name':title.replace(' ',''),'displayName':title,'displayOption':1,'width':1920,'height':1080,'filters':'[]','config':json.dumps({'objects':{'background':[{'properties':{'color':color('#F0F4F8'),'transparency':lit('0D')}}]}}),'visualContainers':[]};report['sections'].append(page)
 textbox('NORTHLINE',16,25,385,58,36,True);textbox('S U P P L Y   /   O P E R A T I O N S',19,87,395,30,11,col='#267B93');textbox(title,440,23,1450,65,36,True)
 v,c,s=visual('cardVisual',440,94,1450,48);bind(s,None,{'Data':[('Report Heading','Reporting period')]});s['objects']={'value':[{'properties':{'horizontalAlignment':lit("'left'"),'fontSize':lit('24D'),'fontColor':color('#267B93')},'selector':{'id':'default'}}],'label':[{'properties':{'show':lit('false')},'selector':{'id':'default'}}]};s['vcObjects']={'background':props(show=lit('false')),'border':props(show=lit('false'))};finish(v,c)
 textbox('Synthetic data | Data Model & Dashboard Design by Norman Lester Cañete',1050,1057,850,22,8,align='right')
 for i,(n,label) in enumerate(kpis):
  st=json.dumps(template).replace('Workforce Trends Measures','Metrics').replace('Workforce Net Change Previous Month',n+' Previous').replace('Workforce Net Change Change Color',n+' Color').replace('Workforce Net Change Change',n+' Change').replace('Workforce Net Change',n).replace('Net Change',label);c=json.loads(st);c['name']=uuid.uuid4().hex[:20];s=c['singleVisual'];x=16+i*316
  for l in c['layouts']:l['position'].update(x=x,y=160,width=304,height=140)
  s['objects']['image']=props(show=lit('false'))
  for group,entries in s['objects'].items():
   for item in entries:
    p=item['properties']
    for k in list(p):
     if 'Color' in k and k!='detailFontColor':p[k]=color('#FFFFFF' if k=='fillColor' else '#267B93' if group=='accentBar' else '#000000')
     if k.endswith('Transparency'):p[k]=lit('0D')
    if group=='referenceLabel':p['backgroundShow']=lit('false')
    if group=='referenceLabelDetail':p['detailFontColor']={'solid':{'color':{'expr':measure(n+' Color',True)}}}
    if group=='referenceLabelValue':p['valuePrecision']=lit('1L' if measures[n][1] in ['0.0','0.0%'] else '0L')
  s['objects']['value'][0]['properties']['labelPrecision']=lit('1L' if measures[n][1] in ['0.0','0.0%'] else '0L');s['columnProperties']['Metrics.'+n]['formatString']=measures[n][1];s['columnProperties']['Metrics.'+n+' Previous']['displayName']='Previous Month';s['vcObjects']={'background':props(show=lit('false')),'border':props(show=lit('false'))};finish({'x':x,'y':160,'width':304,'height':140,'z':1000,'filters':'[]'},c)
 width=(1888-16*(len(slicers)-1))/len(slicers)
 for i,(t,col,label) in enumerate(slicers):
  v,c,s=visual('slicer',16+i*(width+16),310,width,65);bind(s,(t,col,'Values'),{});s['objects']={'data':props(mode=lit("'Dropdown'")),'header':props(show=lit('true'),fontColor=color('#000000'),textSize=lit('11D')),'selection':props(strictSingleSelect=lit('true' if i==0 else 'false'))};s['columnProperties'][t+'.'+col]={'displayName':label}
  if i==0:s['objects']['general']=props(filter={'filter':{'Version':2,'From':[{'Name':'d','Entity':t,'Type':0}],'Where':[{'Condition':{'In':{'Expressions':[column(t,col)],'Values':[[{'Literal':{'Value':"'Aug 2026'"}}]]}}}]}})
  finish(v,c)
def plot(typ,rect,title,cat,roles,secondary=False):
 v,c,s=chart(typ,*rect,title,cat,roles);s['objects']['valueAxis'][0]['properties'].update(secShow=lit('true' if secondary else 'false'),secLabelColor=color('#000000'));s['vcObjects']['title'][0]['properties']['fontSize']=lit('18D');s['objects']['lineStyles']=props(lineChartType=lit("'linear'"),strokeWidth=lit('2D'),showMarker=lit('true'),markerSize=lit('4D'))
 if typ=='barChart':s['objects']['legend']=props(show=lit('false'))
 v['config']=json.dumps(c)
def table(title,cat,fields):
 v,c,s=visual('tableEx',632,706,1272,350,title);bind(s,(cat[0],cat[1],'Values'),{'Values':fields});s['projectionOrdering']={'Values':list(range(len(s['prototypeQuery']['Select'])))};s['objects']={'columnHeaders':props(fontColor=color('#000000'),fontSize=lit('11D'),bold=lit('true'),columnAdjustment=lit("'growToFit'"),wordWrap=lit('true')),'values':props(fontColorPrimary=color('#000000'),fontColorSecondary=color('#000000'),fontSize=lit('11D')),'grid':props(rowPadding=lit('8D')),'total':props(totals=lit('false'))};s['vcObjects']['title'][0]['properties']['fontSize']=lit('18D');finish(v,c)
A=(16,390,928,300);B=(960,390,944,300);C=(16,706,600,350);axis=('Trend Month','Month','Category');warehouse=('Warehouses','Warehouse','Category');category=('Products','Category','Category');supplier=('Suppliers','Supplier','Category');stage=('Stages','Stage','Category')
filters=[('Reporting Month','Month','Reporting month'),('Warehouses','Warehouse','Warehouse'),('Products','Category','Product category'),('Products','SKU','SKU')]
start('Operations Overview',[(n,n) for n in ['Shipped Units','On Time In Full','Due Month Fill Rate','Backlog Units','Inventory Value','Ship Cycle Days']],filters)
plot('lineClusteredColumnComboChart',A,'Shipped Units & OTIF | Last 12 Months',axis,{'Y':[('Shipped Units Trend','Shipped units')],'Y2':[('On Time In Full Trend','OTIF')]},True)
plot('lineClusteredColumnComboChart',B,'Inventory & Backlog Value | Last 12 Months',axis,{'Y':[('Inventory Value Trend','Inventory')],'Y2':[('Backlog Value Trend','Backlog sales value')]})
plot('barChart',C,'Overdue Units by Warehouse',warehouse,{'Y':[('Overdue Units','Overdue units')]})
table('Warehouse Performance | Selected Month',('Warehouses','Warehouse'),[(n,l) for n,l in [('Shipped Units','Shipped units'),('On Time In Full','OTIF'),('Backlog Units','Backlog units'),('Inventory Value','Stock value'),('Aged 90 Share','Aged >90d'),('Ship Cycle Days','Cycle days')]])
start('Inventory Health',[(n,l) for n,l in [('Inventory Value','Inventory Value'),('Inventory Units','On-Hand Units'),('Aged 90 Value','Aged >90 Days'),('Aged 180 Value','Aged >180 Days'),('Aged 90 Share','Aged Stock Share'),('Stockout SKU Days','Stockout SKU-Days')]],filters)
plot('lineClusteredColumnComboChart',A,'Inventory Value & Aging | Last 12 Months',axis,{'Y':[('Inventory Value Trend','Inventory')],'Y2':[('Aged 90 Share Trend','Aged >90d share')]},True)
plot('columnChart',B,'Stored Stock Age | Selected Month',category,{'Y':[('Age 0to30','0–30 days'),('Age 31to60','31–60 days'),('Age 61to90','61–90 days'),('Age 91to180','91–180 days'),('Age Over180','>180 days')]})
plot('barChart',C,'Stockout SKU-Days by Category',category,{'Y':[('Stockout SKU Days','SKU-days')]})
table('SKU Health | Month-End Stock & Rolling Demand',('Products','SKU'),[(n,l) for n,l in [('Inventory Value','Value'),('Aged 90 Value','Aged >90d'),('WIP Value','Picked / packed'),('Turnover 12M','12M turnover'),('Days Cover','90d cover days'),('Stockout SKU Days','Stockout days')]])
start('Order Fulfillment',[(n,n) for n in ['Due Orders','Due Month Fill Rate','On Time In Full','Backlog Orders','Overdue Units','Ship Cycle Days']],filters)
plot('lineChart',A,'Service Levels | Orders Due in Each Month',axis,{'Y':[('Due Month Fill Rate Trend','Due-month unit fill'),('On Time In Full Trend','OTIF orders')]})
plot('lineClusteredColumnComboChart',B,'Backlog & Overdue Units | Month-End',axis,{'Y':[('Backlog Units Trend','Open units')],'Y2':[('Overdue Units Trend','Overdue units')]})
plot('barChart',C,'Open Units by Warehouse Stage',stage,{'Y':[('Backlog Units','Open units')]})
table('Fulfillment by Category | Selected Month',('Products','Category'),[(n,l) for n,l in [('Due Units','Due units'),('Due Month Fill Rate','Fill rate'),('On Time In Full','OTIF'),('Backlog Units','Open units'),('Overdue Units','Overdue'),('Backlog Age','Open age days')]])
start('Supplier Performance',[(n,n) for n in ['Received Units','Receipt Value','Receipt Lead Days','Due Purchase Orders','Supplier OTIF','Late Purchase Orders']],[filters[0],filters[1],('Suppliers','Supplier','Supplier'),filters[2]])
plot('lineClusteredColumnComboChart',A,'Receipt Lead Time & Supplier OTIF | Last 12 Months',axis,{'Y':[('Receipt Lead Days Trend','Unit-weighted lead days')],'Y2':[('Supplier OTIF Trend','Due PO OTIF')]},True)
plot('barChart',B,'Receipt Lead Days by Supplier',supplier,{'Y':[('Receipt Lead Days','Lead days')]})
plot('barChart',C,'Late Purchase Orders by Supplier',supplier,{'Y':[('Late Purchase Orders','Late or not received by promise')]})
table('Supplier Scorecard | Receipts & Due Orders',('Suppliers','Supplier'),[(n,l) for n,l in [('Received Units','Received units'),('Receipt Value','Receipt cost'),('Receipt Lead Days','Lead days'),('Due Purchase Orders','Due POs'),('Supplier OTIF','OTIF'),('Late Purchase Orders','Late POs')]])
start('Warehouse Throughput',[(n,l) for n,l in [('Stage Completions','Stage Unit Completions'),('Stage Capacity','Stage Unit Capacity'),('Capacity Use','Capacity Used'),('Backlog Units','Month-End Queue Units'),('Stage Wait Days','Stage Wait Days'),('Overdue Units','Overdue Queue Units')]],[filters[0],filters[1],('Stages','Stage','Warehouse stage')])
plot('lineClusteredColumnComboChart',A,'Stage Completions & Capacity | Last 12 Months',axis,{'Y':[('Stage Completions Trend','Completed unit tasks')],'Y2':[('Stage Capacity Trend','Available unit tasks')]})
plot('lineChart',B,'Stage Wait Days | Last 12 Months',axis,{'Y':[('Stage Wait Days Trend','Completed-unit weighted wait')]})
plot('barChart',C,'Month-End Queue by Stage',stage,{'Y':[('Backlog Units','Queued units')]})
table('Stage Capacity & Queues | Selected Month',('Stages','Stage'),[(n,l) for n,l in [('Stage Completions','Completed'),('Stage Capacity','Capacity'),('Capacity Use','Used'),('Backlog Units','Queue units'),('Stage Wait Days','Wait days'),('Queue Capacity Days','Queue / daily capacity')]])
# Keep the period caption free of the modern card's default container/padding.
for section in report['sections']:
 for v in section['visualContainers']:
  cfg=json.loads(v['config']); sv=cfg['singleVisual']
  if sv['visualType']=='cardVisual':
   if 'Metrics.Report Heading' in sv.get('columnProperties',{}):
    sv['objects']['value'][0]['properties'].update(bold=lit('false'),fontFamily=lit("'Arial'"))
    sv['objects']['layout']=[{'properties':{'calloutSize':lit('100D')}},{'properties':{'paddingUniform':lit('0L')},'selector':{'id':'default'}}]
    sv['objects']['padding']=[{'properties':{'paddingUniform':lit('0L')},'selector':{'id':'default'}}]
    for group in ['image','referenceLabel','accentBar','divider','outline','fillCustom']:
     sv['objects'][group]=[{'properties':{'show':lit('false')},'selector':{'id':'default'}}]
    sv['objects']['fillCustom'].append({'properties':{'show':lit('false')}})
    sv['vcObjects']['padding']=props(top=lit('0D'),bottom=lit('0D'),left=lit('0D'),right=lit('0D'))
   else:
    for entry in sv['objects'].get('accentBar',[]):entry['properties']['color']=color('#267B93')
  v['config']=json.dumps(cfg)
dump(RR/'report.json',report)
print(f'Built {len(report["sections"])} pages, {len(measures)} measures, {len(tables)} tables')
