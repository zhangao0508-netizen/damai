# 大麦本地运维实验环境

采用真实大麦代码：Docker 承载中间件，Kubernetes 承载八个 Java 服务和 Vue/Nginx 前端。

## 数据隔离

本部署只操作新建的 `damai-lab-*` 容器及 `damai-lab_*` 命名数据卷。不会连接已有 `dev-mysql:3306`，不会向 Navicat 已有连接的数据库导入数据。Navicat 是连接客户端，不是数据库服务；是否隔离取决于实际容器、端口和数据卷。

| 组件 | 新容器 | 本机入口 |
|---|---|---|
| MySQL 8.4 | damai-lab-mysql | 127.0.0.1:13306 |
| Redis 7 | damai-lab-redis | 127.0.0.1:16379 |
| Nacos 2.4.3 | damai-lab-nacos | http://127.0.0.1:18848/nacos |
| Kafka 3.9.1 | damai-lab-kafka | 127.0.0.1:19092 |
| Elasticsearch 7.17 | damai-lab-elasticsearch | http://127.0.0.1:19200 |
| 前端 | K8S damai-web | http://127.0.0.1:18090 |

MySQL 用户 `damai`，密码是 `.local/database-password` 中随机生成的值。不要分享该文件或 `.local/compose.env`。MySQL 第一次启动时初始化 sql/cloud 中的十个数据库；后续发布不会重置数据库。保留 Docker 数据卷，不运行 `down -v`。

## 部署与访问

项目根目录 PowerShell：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File ops/deploy.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File ops/start-web.ps1
```

第二条确保后台入口容器运行，无需保持终端，打开 http://127.0.0.1:18090 。Java 使用本机 `D:/dev/jdk/jdk17`；可通过 DAMAI_JAVA_HOME 指定其他 Java17。Python 优先使用当前 Codex 自带运行时，也可通过 DAMAI_PYTHON 指定。

复用已有 kind 集群 `demo-lab`，独立命名空间 `damai-dev`。集群配置保存在忽略提交的 `.local/kubeconfig`，kind 工具放在 `.local/bin`。在 Headlamp 中切换到 damai-dev，使用之前的 lab-admin Token 可查看管理。

中间件使用专属 Docker 网络 `damai-lab`，网段172.30.88.0/24；kind 节点加入此网络。K8S Service + EndpointSlice 指向中间件容器固定内部 IP，让应用继续使用 mysql、redis、nacos、kafka、elasticsearch 服务名。所有本机发布端口仅绑定127.0.0.1。

## 常用检查

```powershell
$env:KUBECONFIG="$PWD/.local/kubeconfig"
kubectl --context kind-demo-lab -n damai-dev get pods,deployments,services,endpointslices
kubectl --context kind-demo-lab -n damai-dev logs deployment/damai-gateway-service --tail=80
docker compose --env-file .local/compose.env -f ops/.generated/compose.json ps
docker logs damai-lab-mysql --tail=30
powershell -NoProfile -ExecutionPolicy Bypass -File ops/smoke.ps1
```

学习场景可练习数据库持久化、服务注册、分库分表、消息队列、搜索、网关、探针、资源限制和滚动发布。初始数据由原项目提供，节目时间和图片可能较旧。支付保持项目的沙箱模式，部署验证不触发支付操作，不代表已打通真实支付及公网回调。

前端本地构建关闭请求签名，允许原项目自带的普通调用方式，不把浏览器私钥当作安全边界。这套无公网入口的环境只供本机学习。应用配置限制 Actuator 只暴露健康、信息与 Prometheus。

`.generated` 包含生成后的 Secret 定义，不提交；render.py 和 Dockerfile 可以提交。不要把本机 Token、数据库密码、Runner 凭证写入 Git。

首次种子导入发现节目 important_notice 的 varchar(100) 小于原始数据长度，render.py 仅在生成的初始化 SQL 中改为 text，保留原始 SQL 文件。


入口使用独立 damai-lab-entry 容器代理到 K8S NodePort30090，滚动发布更换前端 Pod 后 URL 不变，不依赖临时端口转发。Nginx 保留项目 no_verify 请求头并设置本地渠道0001。监控服务仅开放无详情的健康端点供探针使用，监控页面仍需认证。

自动部署：运行 ops/setup-runner.ps1 注册 damai-local Runner，再运行 ops/start-runner.ps1 保持监听。推送 dev 后，GitHub Actions 构建镜像并更新 damai-dev，最后检查八个服务健康以及372城市、分类和节目查询。Runner 会继承当前仓库的 GitHub 代理设置，电脑、Docker 和代理应保持运行。

首页把全部城市的areaId从0修正为null，与后端SQL约定一致。


SQL 初始化显式 SET NAMES utf8mb4，避免 MySQL 客户端默认 latin1 导致中文二次编码。发布检查会验证中文分类名称。Windows Runner 使用任务级 core.longpaths 配置支持原项目较长的模块路径，不修改全局 Git 设置。
