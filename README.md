# PETCIRCLE 官网本机功能版

主需求与验收依据见 [官网实施记录.md](官网实施记录.md)。

## 打开

- 官网：<http://127.0.0.1:4173/>。
- 后台：<http://127.0.0.1:4173/#/admin>。
- 本机管理员登录信息保存在 `.local/管理员登录.txt`，不要提交到 Git 或对外公开。
- 所有导入产品初始为未上架。后台搜索、勾选后批量上架，勾选“首页精选”，调整顺序。
- 调整客户人民币报价：后台“客户与币种”，按邮箱、公司或联系人查找。
- 新客询价标签与未读提醒在“客户询价”；后台每30秒刷新提醒，打开报价后取消未读，保留首询标签。
- 产品资料由后台“更新产品资料”只读获取正式工作台快照和设置；不会触发ERP同步、改变库存或重置上下架。

## 启动与检查

运行 `python3 scripts/start_local.py` 启动本机服务。脚本使用本机已配置的 Codex Python 运行环境，前端为 `web/` 中的 React + Vite，后端为 `server/` 中的 Python 服务与独立 SQLite 数据库。

自动检查：

```sh
/Users/levenwong/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m unittest server.test_app server.test_languages server.test_categories -v
npm --prefix web run build
npm --prefix web run test:sites
```

数据、密码、测试记录和下载文件均存于被忽略的 `.local/`，不进入源码仓库。测试使用隔离数据库，不修改经营数据。`server/node_modules` 仅链接已配置的 Artifact Tool，PDF 使用运行环境的 ReportLab，Excel 使用 Artifact Tool。

## 验收边界

这是本机功能版，尚未部署到公开域名。站点静态包装检查不代表后台可直接部署到 Sites；账号、库存、报价和下载需要 Python 服务。

价格、库存与工作台单向同步；生成报价时按最新已同步资料检查，不能代替最终人工库存确认，也不占用或扣减库存。中国时间05:30后必须使用当日成功快照。

常规尺码参考复用工作台中英文图，专属款尺寸需按实际款式确认。装箱为参考，不生成虚假的实际箱单。不设付款、站内聊天或自动邮件发送。联系入口打开站内弹窗，展示并复制联系方式；访客无需注册可留下联系方式与需求，管理员在“客户留言”查看，站外自行联系。产品报价下载仍要求注册。

## 视觉依据

选定稿：`design/homepage/hero-lifestyle-revised.png`。桌面首屏沿用大幅花园宠物摄影；下方分类与产品使用工作台真实图片。实际产品上架范围由管理员控制。生产实力使用 `assets/production/materials.json` 中已验收素材。

浏览器验收证据和选定稿对照在 `design/qa/`，详细检查结论见 `design-qa.md`。

## 多语言修改与发布检查

- 新增或修改对客文字时，先核对中英文含义、业务术语及实际按钮动作；不能把“有字典值”当作翻译正确。
- 页面正文、按钮、提示和辅助标签统一走语言层；数字、人名、品牌名、公司法定名称、业务编号各自保留含义，不能机械互换。
- `npm --prefix web run build` 会先自动执行语言检查；裸文字、缺字典项等检查失败会阻止构建。
- 发布前必须运行 `npm --prefix web run check:release`，同时核对当前已上架商品英文资料。`scripts/check_language_release.py` 只读检查，不改上架状态或经营资料。
- 商品英文名称、颜色/图案显示修订维护在 `shared/product-translations.json`，不回写ERP；不明确的规格先人工核对，不能自动写成Assorted。后台标记“英文规格待核对”，未核对不能上架。
- PDF/Excel词汇和单位维护在 `shared/document-messages.json`；新增翻译同时检查页面与文件，历史报价快照不重写。
- 自动检查不能判断所有语义。后续新增内容仍须先做文字审阅；功能完成后按用户授权做浏览器检查，再交人工验收。未通过不发布公网。

## 视觉规范和品牌标识

统一规则见根目录`AGENTS.md`，变量定义在`web/src/design-system.css`，旧组件样式也必须引用该文件的角色。构建前自动运行`npm --prefix web run check:visual-system`，禁止组件自行另写字号、字体及色值。顶栏/页脚商标使用`web/src/brand.jsx`，图形SVG内嵌原始品牌图片，不使用生成预览重画素材。检查仅覆盖源码约束和素材完整性，页面及人工检查仍待统一验收。
