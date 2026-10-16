# Prototype Instructions

## PETCIRCLE 已确认设计方向

- 唯一选定稿为父目录 `design/homepage/hero-lifestyle-revised.png`，用户已确认继续搭建。
- 大幅自然光宠物生活场景海报、现代无衬线文字、少量品牌文案，下接产品。旧 `option-1/2/3.png` 三稿被明确否定，禁止恢复白底商品拼贴配大衬线标题的旧方向。
- 默认英文，支持中文切换。语言预设为中文、英文、俄语、西班牙语；俄语和西班牙语翻译验收前保持隐藏。语言开关以 `../shared/languages.json` 为准，固定页面文案维护于 `src/locales/`，下载文案维护于 `../shared/document-messages.json`，缺失翻译回退英文；管理后台保持中文。真实商品图片用于产品目录，氛围海报不冒充具体在售款。
- 完整业务边界与进度在父目录 `官网实施记录.md`。不添加付款、聊天或自动邮件。2026-10-16用户已确认新增联系方式弹窗及客户留言收集，后台查看后站外联系；不做站内回复。
- 后台单独保存上架选择，不得为填充画面擅自上架经营副本商品。浏览器测试使用隔离数据副本。

Run the local server yourself and open the preview in the browser available to this environment. Do not give the user server-start instructions when you can run it.

Before making substantial visual changes, use the Product Design plugin's `get-context` skill when the visual source is unclear or no longer matches the current goal. When the user gives durable prototype-specific design feedback, preferences, or decisions, record them in `AGENTS.md`.

When implementing from a selected generated mock, treat that image as the source of truth for layout, component anatomy, density, spacing, color, typography, visible content, and hierarchy.

Build app UI in `src/`. Keep `.openai/hosting.json`, `worker/index.js`, `scripts/prepare-sites-build.mjs`, and `tests/sites-worker.test.mjs` intact so the same local prototype can be handed to Sites. Before a Sites handoff, run `npm run build` and `npm run test:sites`; the build must leave `dist/client/index.html`, `dist/server/index.js`, and `dist/.openai/hosting.json`.

## PETCIRCLE 品牌标识规范（2026-10-16 用户确认）

- 品牌主识别为大写文字商标 PETCIRCLE；用户提供的猫狗线条图为辅助图形 logo，存在感克制，不得压过文字。
- 顶部导航左侧：小猫狗图形置于 PETCIRCLE 左侧，图形不带下方手写体；采用缩小后的灰色图形，PETCIRCLE 保持醒目、清晰。不要恢复第一版较大、纯黑图形。
- 页脚品牌区：保留猫狗及下方手写体的完整图形，缩小并降低对比度，配合醒目的 PETCIRCLE 文字；主海报不再重复放大图形 logo。
- 顶部和页脚的 PETCIRCLE 文字末尾 E 的右上角均加小号注册标记 ®（带圈 R），与文字留适当间距；不在猫狗图形或手写体旁另加 ®，不将所有正文品牌提及批量加标。
- 用户说明 PETCIRCLE 为中国、美国均已注册的第18类商标；此为用户提供的信息，未核验注册证，不推定猫狗图形也已注册，不将注册范围扩展到未核定商品。
- 原始图形：`../design/brand/petcircle-graphic-original.png`。最终位置及主次预览：`../design/brand/petcircle-placement-muted-registered-preview.png`。
- 预览用于确定 logo 的位置、大小、主次及 ®，不授权改动其他页面布局或业务。正式实施使用原始素材，保留原始线条，不以生成预览中的重绘图替代原图。
- 当前只完成规范与预览归档，网站尚未应用该 logo 和 ®；不得将效果图当作实装或浏览器验收证据。后续页面修改仍遵守用户验收清单及授权规则。


## 多语言翻译与验收顺序（2026-10-16 用户新增）

- 涉及多语言模块，必须使用专业翻译技能完成翻译，并在上线部署前检查译文准确性。当前未提供可用的专业翻译技能时，应明确说明缺少该技能，先解决技能可用性，不得声称已按专业翻译技能完成。
- 翻译检查须结合实际业务语境，核对品牌与联系人含义、商品名称与规格、按钮动作、错误提示、报价及下载文件用语；不能用字典非空、构建成功或自动测试通过代替语义准确性验收。
- 验收严格按顺序执行：①先检查代码并完成适用的自动检查；②取得用户当前任务明确的浏览器授权后，检查真实页面及网络请求，包括加载、接口响应、语言切换、相关业务流程和下载；③提供检查结果及可直接打开的验收地址，再交用户人工检查，并发出提示音。
- 浏览器步骤不得跳过或冒称完成；缺少授权时说明代码检查结果和待检查项，申请本次授权。此前授权、已登录、测试需要和本条流程约定均不构成本次浏览器授权。前文自动打开预览浏览器的通用指令受此限制。
- 多语言模块在翻译准确性及上述验收流程完成前，不得宣称通过验收或上线部署；部署仍须遵守用户授权边界。

## 2026-10-16 语言修复与发布要求

- 新增内容先审中英文业务含义，再做页面；禁止用name替代品牌概念，联系人Name字段仍表示姓名。
- 先运行`npm run check:languages`；构建已有前置语言检查。发布前再运行`npm run check:release`，核对当前已上架英文商品资料。不得以“字典非空”代替文案审校。
- 对客正文、标题、按钮及辅助标签必须进入语言字典；后台中文文案按原要求保留。联系按钮不得写成直接发邮件或上传图片，实际动作是站内联系弹窗。
- 当前用户要求先做代码检查，功能全部建好后再授权浏览器检查、随后人工验收。没有新授权不得用浏览器。

## 2026-10-16 全站视觉规范的唯一依据

- 全站字体、标题层级、字号、配色、宽度、间距、产品图比例及logo/®尺寸，以项目根目录`../AGENTS.md`第2–7节为唯一依据。新增页面与组件必须使用其中的语义角色，不得各自另选字体颜色。
- 产品目录只显示有有效已上架产品的分类；最大1280px居中、桌面3列、平板及手机2列；主图1:1容器、contain、电脑20px/手机13px内边距。详细字号和断点按根规范，不以旧CSS残留为新模块范本。
- 本轮只归档规范；logo和®的页面实装、旧页面字体/尺寸迁移仍待对应验收清单确认，不将“写进规则”标为“全站已经实现”。

## 2026-10-16 视觉规则与品牌标识已实装本机

- 根规范已通过`src/design-system.css`实施；原`styles.css`使用同一字体字号和颜色变量，不恢复旧的分散硬编码。
- `src/brand.jsx`统一顶栏及页脚PETCIRCLE®，分别使用`public/brand/petcircle-header-original-v1.svg`、`petcircle-footer-original-v1.svg`。SVG直接内嵌原始PNG，通过显示窗口与明度蒙版处理白底，不重画或更改原图。
- ≤600px头部使用两行布局，为logo、语言、账户、询价单和菜单保留空间与触摸范围，不为塞进一行隐藏必要功能。
- 新增`npm run check:visual-system`并接入prebuild：颜色/字体/字号变量门禁、未定义变量检查、SVG原图哈希一致性。尚不能代替浏览器真实显示检查；本轮仍无浏览器授权，后续按统一验收清单处理。
- 本节更新了此前“仅规范未实装”的历史状态；本机代码已实装，公网部署、浏览器和人工验收仍未完成。
