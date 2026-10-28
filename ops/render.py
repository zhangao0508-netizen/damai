import json, secrets, sys, re, os
from pathlib import Path
root = Path(__file__).resolve().parents[1]
tag = sys.argv[1] if len(sys.argv)>1 else 'local'
if not re.fullmatch(r'[A-Za-z0-9_.-]+', tag): raise ValueError('Invalid image tag')
out=root/'ops/.generated'; out.mkdir(parents=True,exist_ok=True)
local=Path(os.environ.get('DAMAI_LAB_HOME', str(root/'.local'))); local.mkdir(parents=True,exist_ok=True)
pwfile=local/'database-password'
if not pwfile.exists(): pwfile.write_text(secrets.token_hex(24))
pw=pwfile.read_text().strip()
ns='damai-dev'
def obj(kind,name,**extra):
    return dict(apiVersion='v1',kind=kind,metadata=dict(name=name,namespace=ns),**extra)
def save(name,items): (out/name).write_text(json.dumps(dict(apiVersion='v1',kind='List',items=items),ensure_ascii=False,indent=2),encoding='utf-8')
def cm(name,data): return obj('ConfigMap',name,data=data)
def env(data): return [dict(name=k,value=str(v)) for k,v in data.items()]
def pvc(name,size): return obj('PersistentVolumeClaim',name,spec=dict(accessModes=['ReadWriteOnce'],resources=dict(requests=dict(storage=size))))
def service(name,ports): return obj('Service',name,spec=dict(selector=dict(app=name),ports=[dict(name='p'+str(p),port=p,targetPort=p) for p in ports]))
def deploy(name,image,ports,environment={},args=None,mounts=[],volumes=[],memory='512Mi',cpu='500m',stateful=False,probe=None):
    c=dict(name=name,image=image,ports=[dict(containerPort=p) for p in ports],env=env(environment),resources=dict(requests=dict(cpu='50m',memory='128Mi'),limits=dict(cpu=cpu,memory=memory)))
    if args: c['args']=args
    if mounts: c['volumeMounts']=mounts
    if probe:
        c['startupProbe']=dict(httpGet=dict(path=probe,port=ports[0]),periodSeconds=5,failureThreshold=120)
        c['readinessProbe']=dict(httpGet=dict(path=probe,port=ports[0]),periodSeconds=10)
        c['livenessProbe']=dict(httpGet=dict(path=probe,port=ports[0]),periodSeconds=30,failureThreshold=5)
    pod=dict(containers=[c])
    if volumes: pod['volumes']=volumes
    spec=dict(replicas=1,selector=dict(matchLabels=dict(app=name)),template=dict(metadata=dict(labels=dict(app=name)),spec=pod))
    if stateful: spec['strategy']=dict(type='Recreate')
    return dict(apiVersion='apps/v1',kind='Deployment',metadata=dict(name=name,namespace=ns),spec=spec)
infra=[dict(apiVersion='v1',kind='Namespace',metadata=dict(name=ns)),obj('Secret','database',type='Opaque',stringData=dict(password=pw))]
initdir=local/'mysql-init'; initdir.mkdir(exist_ok=True)
for f in sorted((root/'sql/cloud').glob('damai_*.sql')):
    db=f.stem
    sql=f'CREATE DATABASE IF NOT EXISTS `{db}` CHARACTER SET utf8mb4;\nUSE `{db}`;\n'+f.read_text(encoding='utf-8-sig').replace('`important_notice` varchar(100)', '`important_notice` text')+f"\nGRANT ALL ON `{db}`.* TO 'damai'@'%';\n"
    (initdir/f.name).write_text(sql,encoding='utf-8')
(local/'compose.env').write_text('DAMAI_DB_PASSWORD='+pw+'\n',encoding='utf-8')
services={}
images={'mysql':'mysql:8.4','redis':'redis:7-alpine','nacos':'nacos/nacos-server:v2.4.3','kafka':'apache/kafka:3.9.1','elasticsearch':'docker.elastic.co/elasticsearch/elasticsearch:7.17.28'}
paths={'mysql':'/var/lib/mysql','redis':'/data','nacos':'/home/nacos/data','kafka':'/var/lib/kafka/data','elasticsearch':'/usr/share/elasticsearch/data'}
portsmap={'mysql':[(13306,3306)],'redis':[(16379,6379)],'nacos':[(18848,8848)],'kafka':[(19092,19092)],'elasticsearch':[(19200,9200)]}
for i,name in enumerate(images,10):
    ip='172.30.88.'+str(i)
    c=dict(image=images[name],container_name='damai-lab-'+name,restart='unless-stopped',networks={'damai-lab':{'ipv4_address':ip}},volumes=[name+'-data:'+paths[name]],ports=['127.0.0.1:'+str(h)+':'+str(t) for h,t in portsmap[name]],mem_limit='1g')
    services[name]=c
    ports=[3306] if name=='mysql' else [6379] if name=='redis' else [8848,9848,9849] if name=='nacos' else [9092] if name=='kafka' else [9200]
    svc=service(name,ports); svc['spec']['selector']=None; infra.append(svc)
    infra.append(dict(apiVersion='discovery.k8s.io/v1',kind='EndpointSlice',metadata=dict(name=name+'-docker',namespace=ns,labels={'kubernetes.io/service-name':name,'endpointslice.kubernetes.io/managed-by':'damai-local-tools'}),addressType='IPv4',ports=[dict(name='p'+str(port),protocol='TCP',port=port) for port in ports],endpoints=[dict(addresses=[ip],conditions=dict(ready=True))]))
services['mysql'].update(environment=dict(MYSQL_ROOT_PASSWORD='${DAMAI_DB_PASSWORD}',MYSQL_USER='damai',MYSQL_PASSWORD='${DAMAI_DB_PASSWORD}',MYSQL_DATABASE='damai_base_data'),command=['--innodb-buffer-pool-size=128M','--max-connections=300'],healthcheck=dict(test=['CMD-SHELL','mysqladmin ping -h localhost -uroot -p"$$MYSQL_ROOT_PASSWORD" --silent'],interval='10s',timeout='5s',retries=30,start_period='60s'))
services['mysql']['volumes'].append(str(initdir).replace('\\','/')+':/docker-entrypoint-initdb.d:ro')
services['redis']['command']=['redis-server','--appendonly','yes','--maxmemory','256mb','--maxmemory-policy','noeviction']
services['nacos']['environment']=dict(MODE='standalone',PREFER_HOST_MODE='hostname',NACOS_AUTH_ENABLE='false',JVM_XMS='128m',JVM_XMX='384m',JVM_XMN='128m')
services['kafka']['environment']=dict(KAFKA_NODE_ID='1',KAFKA_PROCESS_ROLES='broker,controller',KAFKA_LISTENERS='INTERNAL://:9092,CONTROLLER://:9093,EXTERNAL://:19092',KAFKA_ADVERTISED_LISTENERS='INTERNAL://172.30.88.13:9092,EXTERNAL://localhost:19092',KAFKA_CONTROLLER_LISTENER_NAMES='CONTROLLER',KAFKA_INTER_BROKER_LISTENER_NAME='INTERNAL',KAFKA_LISTENER_SECURITY_PROTOCOL_MAP='CONTROLLER:PLAINTEXT,INTERNAL:PLAINTEXT,EXTERNAL:PLAINTEXT',KAFKA_CONTROLLER_QUORUM_VOTERS='1@kafka:9093',KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR='1',KAFKA_TRANSACTION_STATE_LOG_REPLICATION_FACTOR='1',KAFKA_TRANSACTION_STATE_LOG_MIN_ISR='1',KAFKA_LOG_DIRS='/var/lib/kafka/data',KAFKA_HEAP_OPTS='-Xms128m -Xmx384m')
services['elasticsearch']['environment']={'discovery.type':'single-node','xpack.security.enabled':'false','node.store.allow_mmap':'false','ES_JAVA_OPTS':'-Xms256m -Xmx512m'}
compose=dict(name='damai-lab',services=services,volumes={name+'-data':{} for name in services},networks={'damai-lab':dict(name='damai-lab',ipam=dict(config=[dict(subnet='172.30.88.0/24')]))})
(out/'entry.conf').write_text('server { listen 80; underscores_in_headers on; location / { proxy_pass http://demo-lab-control-plane:30090; proxy_set_header Host $host; proxy_set_header no_verify $http_no_verify; } }\n',encoding='utf-8')
compose['services']['entry']=dict(image='nginx:1.27-alpine',container_name='damai-lab-entry',restart='unless-stopped',ports=['127.0.0.1:18090:80'],networks={'damai-lab':{'ipv4_address':'172.30.88.15'}},volumes=[str(out/'entry.conf').replace('\\','/')+':/etc/nginx/conf.d/default.conf:ro'],mem_limit='128m')
(out/'compose.json').write_text(json.dumps(compose,indent=2),encoding='utf-8')
save('infra.json',infra)
props='''spring.data.redis.host=redis
spring.data.redis.port=6379
spring.redis.redisson.threads=4
spring.redis.redisson.netty-threads=4
server.tomcat.threads.max=30
server.tomcat.threads.min-spare=2
spring.cloud.nacos.discovery.server-addr=nacos:8848
spring.cloud.nacos.discovery.username=
spring.cloud.nacos.discovery.password=
spring.kafka.bootstrap-servers=kafka:9092
spring.kafka.admin.fail-fast=false
spring.kafka.consumer.properties.allow.auto.create.topics=true
spring.datasource.username=damai
spring.datasource.password=${DB_PASSWORD}
spring.datasource.hikari.maximum-pool-size=5
spring.datasource.hikari.minimum-idle=1
spring.boot.admin.client.enabled=false
spring.cloud.sentinel.enabled=false
management.endpoints.web.exposure.include=health,info,prometheus
management.endpoint.health.probes.enabled=true
management.endpoint.health.show-details=never
elasticsearch.ip=elasticsearch:9200
elasticsearch.max-connect-num=4
mybatis-plus.configuration.log-impl=org.apache.ibatis.logging.nologging.NoLoggingImpl
orderPayNotifyUrl=http://localhost:18090/api/damai/order/order/alipay/notify
orderPayReturnUrl=http://localhost:18090/order/paySuccess
'''
apps=[cm('application-config',{'application.properties':props})]
shards={}
for name in ['user','program','order','pay']:
    f=root/f'damai-server/damai-{name}-service/src/main/resources/shardingsphere-{name}-local.yaml'
    content=f.read_text(encoding='utf-8-sig').replace('127.0.0.1:3306','mysql:3306').replace('username: root','username: damai').replace('serverTimezone=Asia/Shanghai', 'serverTimezone=Asia/Shanghai&allowPublicKeyRetrieval=true&useSSL=false').replace('password: root',f'password: {pw}').replace('sql-show: true','sql-show: false')
    # Bound per-shard connection pools for a single-machine learning cluster.
    content=content.replace('dataSourceClassName:', 'maximumPoolSize: 5\n    minimumIdle: 1\n    dataSourceClassName:')
    shards[f'shardingsphere-{name}-local.yaml']=content
apps.append(obj('Secret','sharding-config',type='Opaque',stringData=shards))
ports={'gateway':6085,'base-data':6083,'user':6082,'program':6086,'order':6081,'pay':6087,'customize':6084,'admin':6080}
for short,port in ports.items():
    name=f'damai-{short}-service'
    e={'SPRING_CONFIG_ADDITIONAL_LOCATION':'optional:file:/config/','SPRING_PROFILES_ACTIVE':'pro' if short=='gateway' else 'local','JAVA_TOOL_OPTIONS':'-Xms96m -Xmx384m -XX:ActiveProcessorCount=2','SERVER_PORT':str(port),'APP_VERSION':tag}
    if short in shards or short in ['user','program','order','pay']:
        e['SPRING_DATASOURCE_URL']=f'jdbc:shardingsphere:absolutepath:/sharding/shardingsphere-{short}-local.yaml'
    elif short in ['base-data','customize']:
        db='damai_'+short.replace('-','_')
        e['SPRING_DATASOURCE_URL']=f'jdbc:mysql://mysql:3306/{db}?useUnicode=true&characterEncoding=UTF-8&serverTimezone=Asia/Shanghai&allowPublicKeyRetrieval=true&useSSL=false'
    d=deploy(name,f'damai/{short}:{tag}',[port],e,mounts=[dict(name='config',mountPath='/config',readOnly=True),dict(name='sharding',mountPath='/sharding',readOnly=True)],volumes=[dict(name='config',configMap=dict(name='application-config')),dict(name='sharding',secret=dict(secretName='sharding-config'))],memory='768Mi',cpu='1000m',probe='/actuator/health/readiness')
    c=d['spec']['template']['spec']['containers'][0]; c['imagePullPolicy']='Never'; c['env'].append(dict(name='DB_PASSWORD',valueFrom=dict(secretKeyRef=dict(name='database',key='password'))))
    apps += [d,service(name,[port])]
apps += [deploy('damai-web',f'damai/web:{tag}',[80],memory='128Mi',probe='/'),service('damai-web',[80])]
apps[-2]['spec']['template']['spec']['containers'][0]['imagePullPolicy']='Never'
save('apps.json',apps)
print('Rendered infrastructure and application resources. Credentials remain local.')

web_service=apps[-1]
web_service['spec']['type']='NodePort'
web_service['spec']['ports'][0]['nodePort']=30090
save('apps.json',apps)
