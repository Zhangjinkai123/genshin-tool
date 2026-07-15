# 原神个人分析工具

轻量本地 Web 工具，用于导入并分析抽卡记录、圣遗物与角色练度数据。项目不使用数据库，缓存数据以 JSON 文件保存在本地 `data/` 目录。

## 运行

需要 Python 3.10 或更高版本。

```bash
cd genshin-tool
python run.py
```

启动后打开：

```text
http://127.0.0.1:8787
```

## 技术选型

| 层级 | 当前选型 | 说明 |
| --- | --- | --- |
| 后端运行时 | Python 3.10+ | 方便本地直接运行 |
| Web 服务 | Python 标准库 `http.server` / `ThreadingHTTPServer` | 不依赖 Flask、FastAPI 等框架 |
| 抽卡 URL 拉取 | Python 标准库 `urllib` | 只请求 `mihoyo.com` / `hoyoverse.com` 域名 |
| 数据处理 | Python 标准库 `json`、`datetime`、`collections` | 完成标准化、去重、统计和评分 |
| 前端 | 原生 HTML / CSS / JavaScript | 无需安装 Node 依赖或构建 |
| 视觉风格 | Linear 风格 | 浅色背景、细边框、低阴影、高信息密度 |
| 图表 | ECharts 5 | 本地文件 `app/static/vendor/echarts.min.js`，提供 tooltip、坐标轴、饼图和响应式能力 |
| 存储 | 本地 JSON 文件 | 不引入数据库，便于查看、备份和迁移 |

当前版本刻意不引入数据库、前端框架和构建工具，目标是保持个人工具轻量、可控、容易启动。ECharts 已放在项目本地静态目录中，不需要运行时访问 CDN。后续如果功能继续变复杂，可以再升级到 FastAPI、Vue/React 和 SQLite。

## 已实现

- 账号标识、服务器、备注配置
- 通过祈愿历史 URL 拉取抽卡记录
- 抽卡 JSON 导入、字段标准化、校验、去重
- 抽卡统计：总抽数、卡池分布、五星/四星数量、当前垫数、五星平均出货、UP 命中、月度趋势、五星间隔
- 内置本地历史卡池表，按抽卡时间、卡池类型和五星物品自动推断 UP 命中 / 歪；本地表未覆盖时可回退到设置页维护的当前 UP 五星名单
- ECharts 抽卡图表：卡池分布、月度趋势、五星分布、五星间隔、UP 命中、当前垫数
- 圣遗物 JSON 导入、字段标准化、校验、去重，兼容 Inventory Kamera 的 GOOD 导出格式和 +0 圣遗物
- 圣遗物 RV/等效词条累计分、SSS~B 评级、双暴值与评分说明
- 内置评分模板：暴击主 C、反应输出、精通输出、充能副 C、治疗辅助、生命辅助、防御倍率输出
- 圣遗物筛选、排序、详情面板
- 角色练度分析：读取 GOOD 的角色、武器与已装备圣遗物，按常见定位毕业模板评分并给出培养建议
- 圣遗物与角色练度共用逐件副词条等效次数累计的 RV 规则；单件以 SSS~B 评级，角色为五件已装备圣遗物原始累计分；均不设 100 分封顶，等级、天赋、武器和命座仅展示，不参与评分
- 角色圣遗物对照：展示推荐毕业套装，以及当前实际装备的套装和件数
- 角色筛选：按毕业模板、评分排序，以及毕业/优秀/可用/待培养标签快速筛选
- 材料规划：独立页签展示 GOOD 账号材料，支持中文名称与 GOOD key 模糊搜索
- 培养计算：按角色等级、天赋和已装备武器分组计算材料需求、可用库存与缺口；支持旅行者元素形态
- 培养配方一键更新：从 `genshin-db` 下载并缓存角色、天赋、武器与材料配方
- 本地 JSON 缓存读写与清理

## 评分口径

- 单件圣遗物：使用副词条的 `RV/等效词条累计分`。按五星单次副词条的最高数值折算等效次数；暴击、百分比属性、充能和精通采用完整权重，固定攻击/生命/防御采用较低权重。主词条与等级不计入 RV，分数不设 100 分封顶。
- 单件评级：`SSS` 为 RV 50 及以上，`SS` 为 40-49.9，`S` 为 30-39.9，`A` 为 20-29.9，`B` 为 20 以下。
- 模板评分：单独以 0-100 分评估该圣遗物对选定定位的适配度，结合主词条、副词条、等级和双暴；它不会影响 RV 分或 RV 评级。
- 角色练度：只累计五件已装备圣遗物的 RV。角色评级阈值为 `SSS` 220+、`SS` 180+、`S` 140+、`A` 100+、`B` 100 以下；角色等级、天赋、武器与命座仅展示。

## 数据目录

```text
data/
  banners/
    history.json
  default-wishes.json
  default-artifacts.json
  wishes/
    {uid}.json
  artifacts/
  training-recipes.json  # 运行时下载的培养配方缓存
    {uid}.json
  cache/
    {uid}-wish-summary.json
    {uid}-artifact-summary.json
```

## 样例数据

可在页面中直接导入：

- `samples/wishes.json`
- `samples/artifacts.json`

启动时会读取本地的 `data/default-wishes.json` 与 `data/default-artifacts.json`。这两份文件通常包含个人数据，已被 `.gitignore` 排除，不会提交到 GitHub；仓库中保留 `samples/` 下的脱敏样例。

首次克隆后，如需使用默认展示数据，可在本地执行：

```powershell
Copy-Item samples/wishes.json data/default-wishes.json
Copy-Item samples/artifacts.json data/default-artifacts.json
```

之后也可直接在页面中导入自己的抽卡 JSON 或完整 GOOD JSON。

## Inventory Kamera 导入

1. 使用 Inventory Kamera 导出完整 `GOOD` JSON。
2. 在“圣遗物”页导入该文件，可分析圣遗物；`+0` 圣遗物也会保留。
3. 在“角色练度”页导入同一文件，可重新分析角色等级、天赋、武器和已装备圣遗物。
4. 在“材料规划”页导入同一文件，点击“更新培养配方”后即可计算角色、天赋与武器的材料缺口。

GOOD 文件中的 `characters`、`weapons`、`artifacts` 会按角色键名关联；只有已装备的圣遗物会计入对应角色练度。

## 测试

```bash
python -m unittest discover -s tests
```

## 通过 URL 拉取抽卡记录

1. 在游戏内打开祈愿历史。
2. 复制带 `authkey` 的祈愿历史 URL。
3. 在工具左侧填写账号标识并保存。
4. 进入“抽卡”页，将 URL 粘贴到输入框，点击“从 URL 拉取”。

说明：

- 只靠 UID 不能读取抽卡记录，URL 里的 `authkey` 才是官方接口授权信息。
- `authkey` 会过期，过期后需要重新打开祈愿历史并复制新的 URL。
- 官方接口可能返回 `visit too frequently`。工具已内置请求限速、退避重试和国内接口域名兜底；如果仍被限制，等 1-3 分钟后再试。
- 本工具只允许请求 `mihoyo.com` / `hoyoverse.com` 域名，不保存账号密码和登录凭证。

## 接口

- `POST /api/wishes/analyze`
- `POST /api/wishes/fetch`
- `POST /api/artifacts/analyze`
- `GET /api/wishes/default`
- `GET /api/artifacts/default`
- `POST /api/characters/analyze`
- `GET /api/characters/default`
- `GET /api/cache?uid=...`
- `POST /api/cache/wishes`
- `POST /api/cache/artifacts`
- `DELETE /api/cache?uid=...`
