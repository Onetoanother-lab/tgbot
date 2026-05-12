# HomeworkBot — Full Overview

A Telegram bot that manages student homework submissions end-to-end:
submission → pending → teacher review → notifications to student and parents.

---

## Table of Contents

1. [Project Structure](#project-structure)
2. [Tech Stack](#tech-stack)
3. [Environment Variables](#environment-variables)
4. [How the Bot Works — Full Flow](#how-the-bot-works--full-flow)
5. [User Roles](#user-roles)
6. [All Commands](#all-commands)
7. [Group Auto-Registration](#group-auto-registration)
8. [Database Schema](#database-schema)
9. [Notification Matrix](#notification-matrix)
10. [Deployment — Render](#deployment--render)
11. [Known Limitations](#known-limitations)
12. [Feature Ideas](#feature-ideas)

---

## Project Structure

```
tgBot/
├── bot.py            # All handlers, conversation flows, app bootstrap
├── database.py       # SQLite layer — all queries live here
├── messages.py       # All user-facing message templates (Uzbek)
├── requirements.txt  # python-telegram-bot, python-dotenv
├── render.yaml       # Render deployment config
├── .env.example      # Environment variable template
└── homework.db       # Auto-created SQLite database on first run
```

---

## Tech Stack

| Layer | Tool |
|---|---|
| Language | Python 3.10+ |
| Telegram library | `python-telegram-bot` v21.6 |
| Database | SQLite (file-based, no external DB needed) |
| Hosting | Render (free web service tier) |
| Health check | Built-in HTTP server (port from `$PORT`) |
| Config | `.env` via `python-dotenv` |

---

## Environment Variables

Set these in Render → your service → Environment.

| Variable | Required | Description |
|---|---|---|
| `BOT_TOKEN` | ✅ Yes | Token from @BotFather |
| `TEACHER_CHAT_ID` | ⚠️ Optional | Teacher's personal Telegram numeric ID. Get it by running `/myid` in the bot. If set, the teacher also receives submissions as a DM in addition to the teacher group. |
| `DB_PATH` | ❌ No | Path to SQLite file. Defaults to `homework.db` |

> ⚠️ **Render ephemeral disk warning:** Render's free tier does not have persistent disk.
> The `homework.db` file resets on every redeploy. See [Known Limitations](#known-limitations).

---

## How the Bot Works — Full Flow

### Step 1 — Student submits homework

Student opens the bot in private chat and runs `/submit`.
The bot walks them through a 3-step conversation:

```
/submit
  └─► "Enter your full name"
        └─► "Enter your group (e.g. 5A)"
              └─► "Send your homework as photo or document"
                    └─► ✅ Submission saved, notifications sent
```

All three steps must be completed in order.
The student can cancel at any step with `/cancel`.

---

### Step 2 — Notifications are sent immediately

Once the file is received, the bot fires three notifications in parallel:

```
Student  ◄── "Submission received, pending review" (text)

Parents group  ◄── "New homework submitted by [name]" (text)
  (matched by group name, e.g. "5A parents")

Teachers group  ◄── Single message: file + student info + grade buttons
  (all registered groups with "teacher" in their name)

Teacher DM  ◄── Same single message (only if TEACHER_CHAT_ID is set)
```

The teachers group gets **one combined message** — the actual file
(photo or document) with the student details and grade buttons in the caption.
There is no separate forwarded message.

---

### Step 3 — Teacher reviews

Inside the teachers group (or DM), the teacher sees:

```
📄 Submission: #3
👤 Student: Abdullayev Jasur
👥 Group: 5A
📎 Type: Document

[⭐ A'lo] [👍 Yaxshi] [📝 Qoniqarli] [⚠️ Yaxshilash kerak] [❌ Bajarilmagan]
```

**Option A — Inline buttons (recommended):**
1. Teacher taps a grade button
2. Bot asks for written feedback
3. Teacher sends: `/feedback 3 Yaxshi ishlanган, lekin imlo xatolari bor`

**Option B — One-shot command:**
```
/review 3 Yaxshi | Yaxshi ishlanган, lekin imlo xatolari bor
```

---

### Step 4 — Review complete, notifications sent

Once the review is saved:

```
Student  ◄── "Homework reviewed! Grade: Yaxshi. Feedback: ..."
Parents group  ◄── "Review complete. Student: Jasur. Grade: Yaxshi. Feedback: ..."
```

---

## User Roles

| Role | Where they interact | What they can do |
|---|---|---|
| **Student** | Private chat with bot | Submit homework, check status |
| **Teacher** | Teachers group or DM | See submissions, grade, give feedback |
| **Parent** | Parents group (read-only) | Receive submission & review notifications |
| **Admin** | Any group | Register groups, list registered chats |

---

## All Commands

### Student commands (private chat)

| Command | Description |
|---|---|
| `/start` | Show welcome message and command list |
| `/submit` | Start the homework submission flow |
| `/mystatus` | List all your submissions with status and grade |
| `/cancel` | Cancel an in-progress submission |
| `/myid` | Show your Telegram numeric ID |

### Teacher commands (teachers group or DM)

| Command | Description |
|---|---|
| `/pending` | List all submissions currently in pending state |
| `/feedback <id> <text>` | Submit written feedback after tapping a grade button |
| `/review <id> <grade> \| <feedback>` | One-shot review without using buttons |

**`/feedback` example:**
```
/feedback 5 Mavzu to'liq yoritilgan, lekin xulosani kengaytiring
```

**`/review` example:**
```
/review 5 Yaxshi | Mavzu to'liq yoritilgan, lekin xulosani kengaytiring
```

### Admin commands (inside any group)

| Command | Description |
|---|---|
| `/register_parents` | Register the current group as a parents group |
| `/register_teachers` | Register the current group as a teachers group |
| `/chats` | List all registered groups with their type and chat ID |

---

## Group Auto-Registration

When the bot is **added to a group**, it reads the group's title and
auto-registers it based on keywords:

| Group title contains | Registered as |
|---|---|
| `parents` (any case) | Parents group |
| `teacher` (any case) | Teachers group |
| Anything else | Ignored (not registered) |

**Examples that auto-register:**
- `5A parents` → parents
- `10B Parents` → parents
- `Maths Teachers Group` → teachers
- `School Teachers` → teachers

**Manual registration** is also available with `/register_parents` and
`/register_teachers` inside any group.

**Parents group matching logic:**
When a student says their group is `5A`, the bot searches for a registered
parents chat whose title contains both `5A` and `parents` (case-insensitive).
This means `5A parents`, `5a parents`, and `5A Parents Group` all match.

---

## Database Schema

SQLite database with two tables.

### `chats` — registered group chats

```sql
CREATE TABLE chats (
    chat_id   INTEGER PRIMARY KEY,  -- Telegram chat ID (negative for groups)
    title     TEXT NOT NULL,        -- Group title as shown in Telegram
    chat_type TEXT NOT NULL         -- 'parents' or 'teachers'
);
```

### `submissions` — homework submissions

```sql
CREATE TABLE submissions (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id    INTEGER NOT NULL,   -- Telegram user ID of the student
    student_name  TEXT NOT NULL,      -- Name entered during /submit
    group_name    TEXT NOT NULL,      -- Group entered during /submit (uppercase)
    file_id       TEXT NOT NULL,      -- Telegram file_id for re-sending
    file_type     TEXT NOT NULL,      -- 'photo' or 'document'
    status        TEXT NOT NULL DEFAULT 'pending',  -- 'pending' | 'reviewed'
    submitted_at  TEXT NOT NULL,      -- ISO timestamp
    reviewed_at   TEXT,               -- ISO timestamp (NULL until reviewed)
    feedback      TEXT,               -- Teacher's written feedback
    grade         TEXT,               -- Selected grade label (e.g. "👍 Yaxshi")
    reviewer_id   INTEGER             -- Telegram user ID of the reviewer
);
```

---

## Notification Matrix

| Event | Student | Parents group | Teachers group | Teacher DM |
|---|---|---|---|---|
| Homework submitted | ✅ Confirmation | ✅ Pending notice | ✅ File + info + buttons | ✅ if `TEACHER_CHAT_ID` set |
| Review complete | ✅ Grade + feedback | ✅ Grade + feedback | ❌ | ❌ |

---

## Deployment — Render

### render.yaml

```yaml
services:
  - type: web
    name: homework-bot
    runtime: python
    buildCommand: pip install -r requirements.txt
    startCommand: python bot.py
    envVars:
      - key: BOT_TOKEN
        sync: false
      - key: TEACHER_CHAT_ID
        sync: false
      - key: DB_PATH
        value: homework.db
```

### Health check

The bot runs a lightweight HTTP server on `$PORT` (default 8080) in a background
thread. It responds `200 OK` to any GET request. This satisfies Render's health
check requirement so the service stays alive.

### Deploy steps

1. Push all files to a GitHub repo
2. Connect the repo to Render as a **Web Service**
3. Set `BOT_TOKEN` and optionally `TEACHER_CHAT_ID` in Environment
4. Deploy — the bot starts automatically

---

## Known Limitations

### 🔴 Database resets on redeploy (Render free tier)
Render's free tier has no persistent disk. Every time the service redeploys
(manually or after inactivity), `homework.db` is wiped. All submissions and
registered chats are lost.

**Fix options:**
- Upgrade to Render's paid plan with a persistent disk
- Switch to an external database (PostgreSQL via Render, PlanetScale, Supabase, etc.)
- Use a file sync service (not recommended for production)

### 🟡 No homework deadline / subject tracking
The current submission only captures name, group, and file. There is no subject,
deadline, or assignment title attached.

### 🟡 No duplicate submission prevention
A student can run `/submit` multiple times and create multiple submissions.
There is no check for "already submitted today" or "already submitted for this subject."

### 🟡 No teacher authentication
Any user inside a registered teachers group can grade any submission. There is no
admin-only restriction on who can call `/feedback` or `/review`.

### 🟡 Inline grade buttons only work once
After a review is saved, the grade buttons on the original message are not updated
or removed. A second teacher could still tap them but the bot will respond
"already reviewed."

### 🟡 No file download / re-send
The bot stores the Telegram `file_id` but has no command to re-fetch or re-send
a specific submission's file to the teacher on demand.

---

## Feature Ideas

These are features not yet implemented that could enhance the bot significantly.

### High priority

| Feature | What it does |
|---|---|
| **Persistent database** | Move from SQLite to PostgreSQL so data survives redeploys |
| **Subject / assignment title** | Ask the student what subject the homework is for during `/submit` |
| **Deadline tracking** | Teacher sets a deadline per subject; bot warns students who submit late |
| **Duplicate prevention** | Block a second submission from the same student for the same subject on the same day |

### Teacher experience

| Feature | What it does |
|---|---|
| **`/resend <id>`** | Re-send the file for a specific submission to the teacher on demand |
| **`/history <group>`** | Show all submissions from a specific group |
| **Bulk pending digest** | Daily summary of all pending submissions sent to teachers at a fixed time |
| **Edit review** | Allow a teacher to update feedback after submitting it |
| **Teacher-only auth** | Only a specific list of Telegram user IDs can grade submissions |

### Student experience

| Feature | What it does |
|---|---|
| **`/resubmit <id>`** | Replace a pending submission with a corrected file |
| **Reminder** | Bot nudges students who haven't submitted by the deadline |
| **Homework history** | Student can see all past grades and feedback in one place |
| **Subject selection** | Inline buttons during `/submit` to pick subject instead of typing |

### Parent experience

| Feature | What it does |
|---|---|
| **Weekly report** | Auto-posted summary of all grades for the week |
| **Grade stats** | Show average grade per student or per group |
| **Late submission alert** | Notify parents separately when a student submits after the deadline |

### Admin / system

| Feature | What it does |
|---|---|
| **`/stats`** | Overall submission count, reviewed vs pending, per-group breakdown |
| **`/export`** | Admin downloads all submissions as a CSV |
| **Multi-language** | Toggle between Uzbek and Russian |
| **Webhook mode** | Replace polling with Telegram webhooks for faster response and less CPU on Render |
| **Rate limiting** | Prevent a student from spamming `/submit` repeatedly in a short window |