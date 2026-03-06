import json
import requests
BASE='http://localhost:8000/v1'
s=requests.Session()
create=s.post(f'{BASE}/sessions',json={'channel':'web','initialContext':{}})
print('CREATE', create.status_code)
if create.status_code >= 400:
    print(create.text)
    raise SystemExit(1)
body=create.json()
sid=body.get('id') or body.get('sessionId')
print('SESSION', sid)

def send(msg):
    r=s.post(f'{BASE}/interactions/message',json={'sessionId':sid,'content':msg,'channel':'web'})
    print('USER', msg)
    print('STATUS', r.status_code)
    if r.status_code >= 400:
        print('ERR', r.text[:400])
        return {}
    payload=r.json().get('payload',{})
    print('BOT', payload.get('message'))
    data=payload.get('data') if isinstance(payload,dict) else {}
    if isinstance(data,dict):
        for k,v in data.items():
            if isinstance(v,dict) and 'itemCount' in v:
                print('CART',k,v.get('itemCount'),v.get('total'))
    return payload

send('empty cart')
send('add AeroThread Audio Pro to cart')
send('choose default add 2')
last=send('show cart')
print('LAST_PAYLOAD', json.dumps(last)[:500])
