import json,uuid
def lit(v):
    return {'expr': {'Literal': {'Value': str(v)}}}

def color(v):
    return {'solid': {'color': lit("'" + v + "'")}}

def measure(n, entity=False):
    return {'Measure': {'Expression': {'SourceRef': {'Entity' if entity else 'Source': 'Metrics' if entity else 'm'}}, 'Property': n}}

def column(t, c):
    return {'Column': {'Expression': {'SourceRef': {'Source': 'd'}}, 'Property': c}}

def props(**kw):
    return [{'properties': kw}]

def visual(typ, x, y, w, h, title=None):
    c = {'name': uuid.uuid4().hex[:20], 'layouts': [{'id': 0, 'position': {'x': x, 'y': y, 'width': w, 'height': h, 'z': 1000, 'tabOrder': 1000}}], 'singleVisual': {'visualType': typ, 'objects': {}, 'vcObjects': {'background': props(show=lit('true'), color=color('#FFFFFF'), transparency=lit('0D')), 'border': props(show=lit('true'), color=color('#DDE7E4'), radius=lit('9D'))}}}
    s = c['singleVisual']
    if title:
        s['vcObjects'].update(title=props(show=lit('true'), text=lit("'" + title + "'"), fontSize=lit('20D'), fontColor=color('#000000'), fontFamily=lit("'Arial'")), spacing=props(spaceAbovePlotArea=lit('10D')))
    v = {'x': x, 'y': y, 'width': w, 'height': h, 'z': 1000, 'filters': '[]'}
    return (v, c, s)

def bind(s, cat, roles):
    q = {'Version': 2, 'From': [{'Name': 'm', 'Entity': 'Metrics', 'Type': 0}], 'Select': []}
    s['projections'] = {}
    s['columnProperties'] = {}
    if cat:
        t, col, role = cat
        q['From'].append({'Name': 'd', 'Entity': t, 'Type': 0})
        ref = t + '.' + col
        q['Select'].append({**column(t, col), 'Name': ref, 'NativeReferenceName': col})
        s['projections'][role] = [{'queryRef': ref, **({'active': True} if role == 'Category' else {})}]
        q['OrderBy'] = [{'Direction': 1, 'Expression': column(t, col)}]
    for role, ns in roles.items():
        s['projections'].setdefault(role, [])
        for n, label in ns:
            ref = 'Metrics.' + n
            q['Select'].append({**measure(n), 'Name': ref, 'NativeReferenceName': label})
            s['projections'][role].append({'queryRef': ref})
            s['columnProperties'][ref] = {'displayName': label}
    s['prototypeQuery'] = q

def finish(v, c):
    v['config'] = json.dumps(c)
    page['visualContainers'].append(v)

def chart(typ, x, y, w, h, title, cat, roles):
    v, c, s = visual(typ, x, y, w, h, title)
    bind(s, cat, roles)
    s['objects'] = {'legend': props(show=lit('true'), position=lit("'BottomRight'"), fontFamily=lit("'Arial'"), fontSize=lit('8D'), labelColor=color('#000000')), 'categoryAxis': props(labelColor=color('#000000'), showAxisTitle=lit('false')), 'valueAxis': props(labelColor=color('#000000'), showAxisTitle=lit('false')), 'labels': props(show=lit('false'), color=color('#000000'))}
    finish(v, c)
    return (v, c, s)