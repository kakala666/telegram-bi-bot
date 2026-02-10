# 05 - 子Bot设计

## 1. 子Bot职责

每个子Bot是一个双向消息转发机器人，负责：
- 接收终端用户消息，转发给Bot主人
- 接收Bot主人回复，发送给终端用户
- 在回复消息中注入广告小尾巴
- 记录消息映射关系
- 管理终端用户（封禁检查）

## 2. 子Bot运行架构

所有子Bot共享一个 Dispatcher（`sub_dp`），通过中间件注入上下文区分不同Bot。

```
sub_dp (Dispatcher)
  │
  ├── sub_router (Router)
  │     ├── /start handler     → 终端用户欢迎
  │     ├── message handler    → 消息转发（双向）
  │     └── callback handler   → 内联按钮处理
  │
  └── middleware
        └── BotContextMiddleware → 注入 sub_bot_record 到 handler 参数
```

### BotContextMiddleware 工作原理

```python
class BotContextMiddleware(BaseMiddleware):
    """
    每次收到消息时，根据 bot.id 查询数据库，
    将 SubBot 记录注入到 handler 的参数中。
    """
    async def __call__(self, handler, event, data):
        bot: Bot = data["bot"]
        bot_id = bot.id

        # 从数据库/缓存查询该 bot_id 对应的 SubBot 记录
        sub_bot_record = await bot_repo.get_by_bot_id(bot_id)

        if not sub_bot_record:
            return  # Bot不在数据库中，忽略

        if sub_bot_record.status != "active":
            return  # Bot已停止，忽略

        # 注入到 handler 参数
        data["sub_bot"] = sub_bot_record

        return await handler(event, data)
```

Handler 中使用：

```python
@sub_router.message()
async def handle_message(message: Message, bot: Bot, sub_bot: SubBot):
    # sub_bot 由中间件自动注入
    owner_id = sub_bot.owner_id
    ...
```

---

## 3. 终端用户 /start - 欢迎流程

### 触发条件
终端用户首次打开子Bot，或发送 `/start`。

### 交互流程

```
终端用户发送: /start 给 @MyFeedbackBot

子Bot执行:
├─→ 1. 中间件注入 sub_bot 记录
├─→ 2. 查询/创建 BotUser 记录
│      ├─→ 新用户: 创建记录，sub_bots.user_count += 1
│      └─→ 老用户: 更新 last_active
├─→ 3. 检查是否被封禁
│      └─→ 已封禁: 回复 "你已被限制使用此Bot"，结束
└─→ 4. 发送欢迎语

子Bot回复:
┌─────────────────────────────────────────┐
│ {sub_bot.welcome_message}               │
│                                         │
│ 如果没有自定义欢迎语，使用默认:            │
│ "欢迎！请直接发送消息，我们会尽快回复。"    │
└─────────────────────────────────────────┘
```

---

## 4. 终端用户 → Bot主人（消息转发）

### 触发条件
终端用户给子Bot发送任意消息（文字、图片、视频、文件、语音、贴纸等）。

### 完整流程

```
终端用户给 @MyFeedbackBot 发送一条消息

子Bot执行:
│
├─→ 1. 中间件注入 sub_bot 记录
│
├─→ 2. 查询/创建 BotUser 记录
│      ├─→ 新用户: 创建 BotUser，更新 user_count
│      └─→ 老用户: 更新 last_active
│
├─→ 3. 封禁检查
│      └─→ is_blocked=True:
│          子Bot回复终端用户: "你已被限制使用此Bot"
│          流程结束
│
├─→ 4. 构建用户信息头
│      user_header = "👤 {display_name}"
│      如果有username: user_header += " (@{username})"
│      user_header += " [ID:{user_id}]"
│
├─→ 5. 根据消息类型转发
│      │
│      ├─→ 5a. 文本消息:
│      │   向Bot主人发送:
│      │   ┌─────────────────────────────┐
│      │   │ 👤 张三 (@zhangsan) [ID:123] │
│      │   │ ━━━━━━━━━━━━━━━              │
│      │   │ 你好，我想咨询一下...          │
│      │   └─────────────────────────────┘
│      │   方法: bot.send_message(
│      │       chat_id=owner_id,
│      │       text=f"{user_header}\n━━━━━━━━━━━━━━━\n{message.text}"
│      │   )
│      │
│      ├─→ 5b. 图片消息:
│      │   向Bot主人发送:
│      │   方法: bot.send_photo(
│      │       chat_id=owner_id,
│      │       photo=message.photo[-1].file_id,
│      │       caption=f"{user_header}\n━━━━━━━━━━━━━━━\n{message.caption or ''}"
│      │   )
│      │
│      ├─→ 5c. 视频消息:
│      │   方法: bot.send_video(chat_id=owner_id, video=..., caption=...)
│      │
│      ├─→ 5d. 文件消息:
│      │   方法: bot.send_document(chat_id=owner_id, document=..., caption=...)
│      │
│      ├─→ 5e. 语音消息:
│      │   方法: bot.send_voice(chat_id=owner_id, voice=..., caption=user_header)
│      │
│      ├─→ 5f. 视频笔记:
│      │   先发送 user_header 文本，再 copy_message
│      │
│      ├─→ 5g. 贴纸:
│      │   先发送 user_header 文本，再 bot.send_sticker(...)
│      │
│      └─→ 5h. 其他类型（位置、联系人等）:
│          先发送 user_header 文本，再 copy_message
│
├─→ 6. 记录消息映射
│      MessageMap(
│          sub_bot_id = sub_bot.id,
│          user_id = user.user_id,
│          user_msg_id = message.message_id,        # 用户发的原始消息ID
│          forwarded_msg_id = sent_message.message_id,  # 转发给主人的消息ID
│          direction = "in"
│      )
│
├─→ 7. 更新统计
│      sub_bots.message_count += 1
│
└─→ 8. 完成（不回复终端用户，静默转发）
```

### 转发失败处理

```
如果转发给Bot主人失败:
├─→ TelegramForbiddenError (主人屏蔽了Bot):
│   - 记录日志
│   - 不回复终端用户（避免暴露内部状态）
│   - 标记 sub_bot.status = 'error'
│
├─→ TelegramBadRequest (消息格式问题):
│   - 尝试用 copy_message 作为降级方案
│   - 如果仍然失败，回复终端用户: "消息发送失败，请稍后重试"
│
└─→ 其他网络错误:
    - 记录日志
    - 不回复终端用户
```

---

## 5. Bot主人 → 终端用户（回复路由）

### 触发条件
Bot主人在与子Bot的聊天中，**回复**一条转发过来的消息。

### 判断逻辑：如何区分Bot主人和终端用户

```python
@sub_router.message()
async def handle_message(message: Message, bot: Bot, sub_bot: SubBot):
    user_id = message.from_user.id

    if user_id == sub_bot.owner_id:
        # 这是Bot主人发的消息
        await handle_owner_message(message, bot, sub_bot)
    else:
        # 这是终端用户发的消息
        await handle_user_message(message, bot, sub_bot)
```

### Bot主人回复的完整流程

```
Bot主人在子Bot聊天中回复一条转发消息

子Bot执行:
│
├─→ 1. 确认是Bot主人（user_id == sub_bot.owner_id）
│
├─→ 2. 检查是否是回复消息
│      └─→ message.reply_to_message 为空:
│          这是Bot主人主动发的消息（不是回复）
│          子Bot回复: "请回复一条转发的消息来回复用户。
│                     如需广播，请使用主Bot的 /broadcast 命令。"
│          流程结束
│
├─→ 3. 查找消息映射
│      forwarded_msg_id = message.reply_to_message.message_id
│      mapping = MessageMap.query(
│          sub_bot_id = sub_bot.id,
│          forwarded_msg_id = forwarded_msg_id
│      )
│      └─→ 找不到映射:
│          子Bot回复Bot主人: "找不到该消息的原始用户，可能消息记录已过期。"
│          流程结束
│
├─→ 4. 获取目标用户
│      target_user_id = mapping.user_id
│      bot_user = BotUser.query(sub_bot_id, target_user_id)
│
├─→ 5. 广告注入
│      │
│      ├─→ 5a. 文本消息:
│      │   original_text = message.text
│      │   text_with_ad = AdInjectorService.inject(original_text, sub_bot.id)
│      │   结果:
│      │   ┌─────────────────────────────┐
│      │   │ 你好，感谢你的咨询...         │
│      │   │                             │
│      │   │ ━━━━━━━━━━━━━━━             │
│      │   │ 📢 Powered by @PlatformBot  │
│      │   └─────────────────────────────┘
│      │
│      ├─→ 5b. 带caption的媒体消息:
│      │   caption_with_ad = AdInjectorService.inject(caption, sub_bot.id)
│      │   发送媒体时使用注入后的caption
│      │
│      └─→ 5c. 无caption的媒体（贴纸、语音等）:
│          先发送媒体（copy_message）
│          再单独发送一条广告文本消息
│
├─→ 6. 发送给终端用户
│      │
│      ├─→ 6a. 文本消息:
│      │   bot.send_message(chat_id=target_user_id, text=text_with_ad)
│      │
│      ├─→ 6b. 图片:
│      │   bot.send_photo(chat_id=target_user_id, photo=..., caption=caption_with_ad)
│      │
│      ├─→ 6c. 其他媒体: 类似处理
│      │
│      └─→ 发送失败:
│          ├─→ TelegramForbiddenError: 用户已屏蔽Bot
│          │   标记 bot_user.is_banned_by_telegram = True
│          │   回复Bot主人: "发送失败，该用户已屏蔽Bot"
│          │
│          └─→ 其他错误:
│              回复Bot主人: "发送失败: {error}"
│
├─→ 7. 记录消息映射（反向）
│      MessageMap(
│          sub_bot_id = sub_bot.id,
│          user_id = target_user_id,
│          user_msg_id = sent_to_user.message_id,
│          forwarded_msg_id = message.message_id,
│          direction = "out"
│      )
│
├─→ 8. 发送确认给Bot主人
│      子Bot回复Bot主人: "✓ 消息已发送给 {display_name}"
│      （使用 reply_to_message_id 回复原消息，保持上下文）
│
└─→ 9. 更新统计
       sub_bots.message_count += 1
```

---

## 6. 消息类型支持矩阵

| 消息类型 | 用户→主人 | 主人→用户 | 广告注入方式 |
|----------|-----------|-----------|-------------|
| 文本 | send_message + 用户头 | send_message + 广告尾 | 追加到文本末尾 |
| 图片 | send_photo + 用户头caption | send_photo + 广告尾caption | 追加到caption末尾 |
| 视频 | send_video + 用户头caption | send_video + 广告尾caption | 追加到caption末尾 |
| 文件 | send_document + 用户头caption | send_document + 广告尾caption | 追加到caption末尾 |
| 音频 | send_audio + 用户头caption | send_audio + 广告尾caption | 追加到caption末尾 |
| 语音 | send_voice + 用户头caption | copy_message + 单独广告消息 | 单独发送广告消息 |
| 视频笔记 | 用户头文本 + copy_message | copy_message + 单独广告消息 | 单独发送广告消息 |
| 贴纸 | 用户头文本 + send_sticker | send_sticker + 单独广告消息 | 单独发送广告消息 |
| 位置 | 用户头文本 + copy_message | copy_message + 单独广告消息 | 单独发送广告消息 |
| 联系人 | 用户头文本 + copy_message | copy_message + 单独广告消息 | 单独发送广告消息 |

---

## 7. 消息映射详解

### 映射记录示例

```
场景: 用户A给子Bot发消息，Bot主人回复

1. 用户A发送 "你好" (msg_id=100 in 用户A的聊天)
   → 子Bot转发给Bot主人 (msg_id=500 in Bot主人的聊天)
   → 记录: MessageMap(user_id=A, user_msg_id=100, forwarded_msg_id=500, direction="in")

2. Bot主人回复 msg_id=500 (Bot主人发送 msg_id=501)
   → 子Bot查找: forwarded_msg_id=500 → 找到 user_id=A
   → 子Bot发送给用户A (msg_id=101 in 用户A的聊天)
   → 记录: MessageMap(user_id=A, user_msg_id=101, forwarded_msg_id=501, direction="out")
```

### 映射查找流程

```python
async def find_target_user(sub_bot_id: int, replied_msg_id: int) -> int | None:
    """根据Bot主人回复的消息ID，找到原始终端用户"""
    mapping = await message_map_repo.get_by_forwarded_msg(
        sub_bot_id=sub_bot_id,
        forwarded_msg_id=replied_msg_id
    )
    if mapping:
        return mapping.user_id
    return None
```

---

## 8. 多用户并发场景

```
时间线:
  T1: 用户A 发送 "问题1" → 转发给主人 (msg_id=500)
  T2: 用户B 发送 "问题2" → 转发给主人 (msg_id=501)
  T3: 用户C 发送 "问题3" → 转发给主人 (msg_id=502)
  T4: 主人回复 msg_id=501 → 查映射 → 发给用户B
  T5: 主人回复 msg_id=500 → 查映射 → 发给用户A
  T6: 主人回复 msg_id=502 → 查映射 → 发给用户C

Bot主人看到的聊天:
┌─────────────────────────────────────────┐
│ 👤 用户A (@a) [ID:111]                   │
│ ━━━━━━━━━━━━━━━                         │
│ 问题1                                    │
│                                         │
│ 👤 用户B (@b) [ID:222]                   │
│ ━━━━━━━━━━━━━━━                         │
│ 问题2                                    │
│                                         │
│ 👤 用户C (@c) [ID:333]                   │
│ ━━━━━━━━━━━━━━━                         │
│ 问题3                                    │
│                                         │
│ (主人回复"问题2"的消息)                    │
│ > 回复B的问题...                          │
│ ✓ 消息已发送给 用户B                      │
└─────────────────────────────────────────┘

关键: 主人必须通过"回复"特定消息来指定回复对象。
如果主人直接发送消息（不回复），子Bot会提示需要回复特定消息。
```

---

## 9. 子Bot的 /start 参数处理

支持 deep link 参数：

```
用户点击链接: https://t.me/MyFeedbackBot?start=ref_12345

子Bot收到: /start ref_12345

处理逻辑:
├─→ 解析参数 "ref_12345"
├─→ 记录到 BotUser 的来源字段（可选扩展）
└─→ 正常执行欢迎流程
```

---

## 10. 错误恢复机制

### Token 失效检测

```
子Bot polling 过程中收到 401 Unauthorized:
├─→ 1. 标记 sub_bot.status = 'token_invalid'
├─→ 2. 从 BotRegistry 移除该Bot
├─→ 3. 通过主Bot通知Bot主人:
│      "你的Bot @xxx 的Token已失效，请重新注册。"
└─→ 4. 记录日志
```

### 网络中断恢复

```
aiogram 内置 backoff 重试机制:
BackoffConfig(min_delay=1.0, max_delay=5.0, factor=1.3, jitter=0.1)

polling 断开后自动重连，无需额外处理。
```
