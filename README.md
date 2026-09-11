# Official Domain Registry v2

v2 架构:FastAPI(异步) + PostgreSQL/Alembic + JWT/API Key 认证 + Vue 前端 + Docker/CI。
v1 仓库:official-domain-registry-mvp-final(线上运行中,API 语义保持兼容)。

## 架构

```text
backend/          FastAPI 异步后端
  app/            main(公共 API) / admin_app(管理 API) / models / routers
  alembic/        PostgreSQL 迁移
frontend/         Vue 3 + Vite(阶段 2)
infra/            docker-compose + nginx(阶段 3)
```

## 本地开发

```bash
cd backend
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt
copy ..\.env.example .env

# 本地默认用 SQLite(零安装),生产用 PostgreSQL
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

接口:Swagger `/docs`,`/api/v1/health`。

## 认证(v2 新)

- `POST /api/v1/auth/register` 注册(返回 JWT 对)
- `POST /api/v1/auth/login` 登录(返回 access+refresh)
- 请求头 `Authorization: Bearer <access_token>`
- 第三方厂商:API Key(前缀 `odrk.`),后续在管理端签发
- 管理员:`is_admin` 角色 + `Depends(require_admin)`

## 可观测性

- 结构化 JSON 日志(structlog)
- `GET /metrics` Prometheus 指标(请求数/耗时)

## 阶段路线

1. ✅ 后端地基:异步 FastAPI + 模型 + Alembic + JWT + 指标
2. ✅ 全量功能移植 + Vue 前端(公共站 + 后台)+ API Key 通道
3. ✅ nginx 反代 + Docker Compose + CI/CD 流水线 + 插件 v2 适配(未线上切换)

## 部署(v2,待切换)

```bash
# 服务器安装 docker + compose plugin + rsync 后:
git clone <repo> /opt/odr-v2
cd /opt/odr-v2
export JWT_SECRET=... ADMIN_PASSWORD=... POSTGRES_PASSWORD=...
docker compose up -d --build      # postgres + backend + backend-admin + frontend(nginx) + tunnel
```

- nginx(`infra/nginx.conf`):SPA 静态 + `/api/*`→backend + `/api/v1/admin/*`→backend-admin + `/metrics`
- 隧道(`infra/cloudflared/config.yml`):registry/admin 两个主机名都指向 frontend:80,填入凭据即可
- GitHub Actions:`.github/workflows/ci.yml`(测试+构建)、`deploy.yml`(rsync 同步 + docker compose 部署,需配 SERVER_HOST/SERVER_SSH_KEY 等 secrets)

## 插件(v2)

`extension/` 已适配 v2:改用 **API Key 认证**(网站个人中心生成 `odrk.` 前缀 Key 填入插件),自动提交默认关闭,浏览器加载 `extension` 目录即可。

## 前端(Vue 3 + Vite)

```bash
cd frontend
npm install
npm run dev        # http://localhost:5173,/api 自动代理到 8000,/api/v1/admin 到 8001
npm run build      # 产物 dist/
```

页面:首页(提交)/ 域名库(组织分组折叠)/ 登录 / 注册(图形验证码+邮箱验证码)/ 个人中心(我的域名+所有权验证+改邮箱)/ 后台(登录/审核队列批量操作/组织管理/用户管理)。

## 测试

```bash
cd backend
python -m pytest tests -q
```
