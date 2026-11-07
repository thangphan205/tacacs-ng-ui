# Alert Rules & Anomaly Detection — Full Workflow

## Alert Rules

### 1. Rule Storage

```
AlertRule (DB table: alertrule)
  name, description, enabled, is_system
  log_type           → "auth" | "authz" | "config" | "all"
  condition_field    → "fail_count" | "deny_count" | "username" | "client_ip" | "config_action" | "login_hour"
  condition_operator → "gt" | "lt" | "eq" | "new_value" | "any_change" | "created" | "updated" | "deleted" | "activated" | "unusual"
  threshold          → float (min count to trigger)
  time_window_minutes → how far back to query
  severity           → "low" | "medium" | "high" | "critical"
  cooldown_minutes   → min gap between re-fires
  last_fired_at      → timestamp of last trigger
```

### 2. Background Loop

**File:** `backend/app/main.py`

```
FastAPI lifespan
  └─ asyncio.create_task(_alert_evaluation_loop())
       └─ loop forever:
            await asyncio.sleep(300)   ← every 5 minutes
            evaluate_all_rules(session)
```

### 3. Cooldown Gate

**File:** `backend/app/crud/alert_rules.py` — `get_rules_due_evaluation()` (line 64)

```
for each enabled AlertRule:
  if last_fired_at is None → include (never fired)
  else:
    elapsed = (now - last_fired_at).total_seconds() / 60
    if elapsed >= cooldown_minutes → include
    else → skip (still in cooldown)

returns: list[AlertRule]
```

### 4. Rule Evaluation

**File:** `backend/app/crud/alert_evaluator.py` — `evaluate_all_rules()` (line 21)

```
channels = all NotificationChannel WHERE enabled=True

for each due rule:
  triggered, payload = _evaluate_rule(rule)

  if triggered:
    payload += { node: NODE_NAME, fired_at: now in the log timezone }
    if no channels:
      create AlertEvent(rule_id, channel_id=NULL, status="no_channel")
    message = build_alert_message(rule, payload)   ← alert_formatter.py
    for each channel:
      success, err = dispatch_notification(channel, message.subject,
                                           render_text(message), payload, message)
      create AlertEvent(rule_id, channel_id, status, error_message)
    set rule.last_fired_at = now   ← the same instant the window ended at
```

### 5. Rule Check Dispatch

**File:** `backend/app/crud/alert_evaluator.py` — `_evaluate_rule()` (line 66)

```
now = datetime.now(utc)
window_start = now - timedelta(minutes=rule.time_window_minutes)

if log_type in ("auth", "all"):   → _check_auth_stats(window_start)
if log_type in ("authz", "all"):  → _check_authz_stats(window_start)
if log_type in ("config", "all"): → _check_audit_logs(window_start)
```

### 6a. Auth Stats Check

**File:** `backend/app/crud/alert_evaluator.py` — `_check_auth_stats()` (line 90)

```
Source table: authentication_statistics
  columns: username, user_source_ip, fail_count, success_count, log_date

condition_field="fail_count", operator="gt/lt/eq":
  total = SUM(fail_count) WHERE log_date >= window_start
  triggered = _compare(total, operator, threshold)

condition_field="username", operator="new_value":
  recent   = DISTINCT username WHERE log_date >= window_start
  baseline = DISTINCT username WHERE log_date in [day(window_start-30d), day(window_start)]
             (log_date is the log file's local day; day() maps an instant to it)
  triggered = (recent - baseline) is not empty

condition_field="client_ip", operator="new_value":
  same as username but on user_source_ip column

condition_field="client_ip", operator="gt/lt/eq":
  fail_by_ip = auth failures in the window grouped by source IP
  matches    = [ip for ip, count in fail_by_ip if _compare(count, operator, threshold)]
  triggered  = matches is not empty
  payload    = { ip, fail_count, triggered_ips: [{ip, fail_count}, ...] }

  Only reached when log_type is "auth" or "all"; use "auth" and operator "gt"
  with an explicit threshold. See the limitations note in the v0.5.3 release
  notes before using "lt"/"eq" or leaving the threshold blank.
```

### 6a-2. Login at Unusual Hour

**Files:** `backend/app/crud/login_hours.py`, `alert_evaluator._check_login_hours()`

`condition_field="login_hour"`, `condition_operator="unusual"`. `threshold` is
the **maximum share of the user's logins, in percent** (default 2).

```
Baseline  AuthenticationHourlyStatistics: successful logins per user and hour
          of day (log timezone), summed over all nodes, for the 30 log days
          before the window's first day. The window's own days are left out:
          the stats run has already partly counted them, so a login would be
          part of its own history.

for each successful login in the window with time >= max(window_start, last_fired_at):
  skip the user if the baseline spans fewer than 7 days (new accounts are
       the New Username rule's job)
  share = logins in {hour-1, hour, hour+1} / all baseline logins  (wraps midnight)
  unusual if share < threshold

payload = { unusual_logins: [{ username, login_at, hour, share, logins,
            total_logins, usual_hours[], source_ips[], devices[] }], … }
          one row per user, rarest first; login_at/hour/share describe the
          earliest unusual login, logins counts all of them in the window.
          usual_hours = hours holding at least 5 % of the user's logins.
```

The neighbouring hours absorb daylight saving and logins near an hour's edge.
A share, rather than "never logged in at this hour", keeps one stray night
login from making that hour normal for the next 30 days.

**Off by default.** `[System] Login at Unusual Hour` is created disabled
(window 10 min, cooldown 5 min, so a login during a cooldown is not missed and
`last_fired_at` stops repeats). Turn it on with the switch in the Alert Rules
table once history has built up. Like every system rule it is only created,
never overwritten, so an admin's choice and threshold survive restarts.

**Collecting the baseline.** `AuthenticationHourlyStatistics` (`node_name,
username, log_date, hour, success_count, fail_count`) is filled on every
authentication stats run, whether or not the rule is enabled, from the same
pass over the log file. On HA, a standby's hourly counts come back in the
`authentication_hourly` key of `collect-stats`; a peer on an older version
omits it and is simply skipped. To fill history from log files still on disk,
run `python scripts/tacacs_logs_authentication.py YYYY-MM-DD` for each day.

Limit: like the other auth rules, the real-time check reads this node's log
files, so a login on a standby is judged only once collected.

### 6b. Authz Stats Check

**File:** `backend/app/crud/alert_evaluator.py` — `_check_authz_stats()` (line 157)

```
Source table: authorization_statistics
  columns: username, deny_count, permit_count, log_date

operator="gt/lt/eq":
  total = SUM(deny_count) WHERE log_date >= window_start
  triggered = _compare(total, operator, threshold)
```

### 6c. Config Audit Check

**File:** `backend/app/crud/alert_evaluator.py` — `_check_audit_logs()` (line 178)

```
Source table: auditlog
  columns: action, entity_type, created_at, user_email, ...

action_map = {
  "any_change" → ["CREATE", "UPDATE", "DELETE", "ACTIVATE"]
  "created"    → ["CREATE"]
  "updated"    → ["UPDATE"]
  "deleted"    → ["DELETE"]
  "activated"  → ["ACTIVATE"]
}

since = max(window_start, rule.last_fired_at)   ← never re-report rows the
                                                   previous firing sent
count = COUNT(*) WHERE entity_type="TacacsConfig"
                   AND action IN action_map[operator]
                   AND created_at >= since

triggered = count >= threshold
changes   = newest 10 rows as { action, filename, entity_id, by, ip_address, at }
            filename from the audit row's new_values (old_values for DELETE)
            at is ISO 8601 in the log timezone
```

### 7. ACTIVATE Audit Log

**File:** `backend/app/api/routes/tacacs_configs.py` — update route

```
old_active = json.loads(old_values)["active"]
if not old_active AND db_tacacs_config.active:
  log_entity_action(action="ACTIVATE", entity_type="TacacsConfig", ...)
```

Written in addition to the standard UPDATE log when a config's `active` field flips `false → true`.

### 8. Notification Message

**File:** `backend/app/crud/alert_formatter.py` — `build_alert_message()`

Every message answers what happened, who, from where, on which device, when,
and on which node, and ends with a link to the page to investigate
(`FRONTEND_HOST` + `/aaa_statistics` or `/audit_logs`). Times are in the log
timezone (TACACS NG Settings). Lists stop at 10 entries (`… +N more`); a
successful login by a *new* username or from a *new* source IP is called out
on its own line, because that is the case that needs a look first.

```
🟠 MEDIUM · New Username Detected

2 usernames not seen in the past 30 days appeared in the last 60 min.
⚠️ Logged in successfully: abc

👤 abc — ✅ 2 ok · ❌ 3 failed
   Source: 192.168.252.1
   Device: core-sw1 (10.1.1.1)
   Seen: 2026-11-07 21:02:11 +07 → 21:07:40

Node primary · fired 2026-11-07 21:08:00 +07
Open: https://tacacs.example.com/aaa_statistics
```

```
🚨 CRITICAL · TACACS Config Activated

1 TACACS config activation in the last 5 min.

1. 🚀 ACTIVATE tacacs_2100.cfg
   By: admin@example.com from 10.0.0.4
   At: 2026-11-07 21:00:25 +07
```

Threshold rules state the condition in words and list the top contributors:
`14 failed logins in the last 10 min (threshold > 10).` followed by
`Top users`, `Top sources` and `Top devices`.

The device name comes from the **Hosts** page: a NAS IP is matched against each
host's IPv4/IPv6 address or network, most specific first (a `/0` catch-all is
ignored). An unmatched device is shown by IP.

Usernames, IPs, filenames and emails are code-formatted and escaped per
channel, so a crafted value cannot inject markup.

### 9. Notification Dispatch

**File:** `backend/app/crud/notification_dispatcher.py` — `dispatch_notification()`

```
parse channel.config_json → dict
subject = "[SEVERITY] <rule name without the [System] prefix>"

channel_type="telegram":
  POST https://api.telegram.org/bot{token}/sendMessage
  body: { chat_id, text=<message as HTML>, parse_mode="HTML",
          disable_web_page_preview=true }
  optional: message_thread_id=topic_id  ← for supergroup forum topics

channel_type="slack":
  POST webhook_url
  body: { text=subject, blocks=[header, divider, mrkdwn section, divider] }

channel_type="discord":
  POST webhook_url
  body: { embeds=[{ title, description=<markdown>, color by severity }] }

channel_type="teams":
  POST webhook_url
  body: AdaptiveCard JSON with subject + plain-text body

channel_type="gchat":
  POST webhook_url
  body: { text=<message with *bold* and `code`> }

channel_type="email":
  SMTP; HTML part = escaped message in <pre>, text part = plain body

channel_type="webhook":
  POST webhook_url
  headers: { Authorization: "Bearer {token}" }  if token present
  body: { subject, body, data }
    data — the structured alert payload (also stored as the alert's
    payload_snapshot). Webhook is the only channel type that receives it.
    Always: rule, window_minutes, node, fired_at (ISO 8601, log timezone).
      username new_value  → new_usernames, users[]
      client_ip new_value → new_source_ips, sources[]
        users[]/sources[] rows: { username | ip, success, fail,
          source_ips | usernames, devices, first_seen, last_seen }
      login_hour unusual  → unusual_logins[] (see 6a-2)
      client_ip gt/lt/eq  → ip, fail_count, triggered_ips[{ip, fail_count}], sources[]
      fail_count gt/lt/eq → fail_count, top_users, top_sources, top_devices
      authz gt/lt/eq      → deny_count, top_users, top_devices
        top_*: [{ name, count }], highest first
      config              → config_change_count, changes[]

The test button sends subject + body to every channel type unchanged.

returns: (success: bool, error_message: str | None)
timeout: 10 seconds
```

### 10. Alert Event Record

```
AlertEvent (DB table: alertevent)
  rule_id          → FK → AlertRule   (CASCADE delete)
  channel_id       → FK → NotificationChannel (SET NULL on delete; NULL for no_channel)
  triggered_at     → timestamp
  payload_snapshot → JSON string (metrics that triggered the rule)
  status           → "sent" | "failed" | "no_channel"
  error_message    → error detail if failed

UI: /alert_events
```

---

## Anomaly Detection

### 1. Background Loop

**File:** `backend/app/main.py`

```
FastAPI lifespan
  └─ asyncio.create_task(_ml_scoring_loop())
       └─ await asyncio.sleep(60)      ← 60s startup delay
          loop forever:
            run_daily_anomaly_scoring(session)
            await asyncio.sleep(86400) ← every 24 hours
```

### 2. Manual Retrain

```
POST /api/v1/anomaly_detection/retrain/   (superuser only)
  → run_daily_anomaly_scoring(session)
```

**File:** `backend/app/api/routes/anomaly_detection.py`

### 3. Feature Extraction

**File:** `backend/app/crud/anomaly_detection.py` — `get_feature_matrix()` (days=30)

```
Query authentication_statistics (last 30 days):
  per username:
    fail_counts = list of daily fail_count values
    unique_ips  = set of distinct user_source_ip

Query authorization_statistics (last 30 days):
  per username:
    total_deny, total_permit

Per username → feature vector (4 dimensions):
  avg_daily_fails  = mean(fail_counts)
  stddev_fails     = stdev(fail_counts)   or 0.0 if single day
  unique_ip_count  = len(unique_ips)
  deny_ratio       = total_deny / (total_deny + total_permit)  or 0.0

Output: { username → { avg_daily_fails, stddev_fails, unique_ip_count, deny_ratio } }
```

### 4. ML Scoring

**File:** `backend/app/crud/ml_anomaly_scorer.py` — `run_daily_anomaly_scoring()`

```
features = get_feature_matrix(session, days=30)

X = numpy array shape (n_users, 4)

model = IsolationForest(
  n_estimators=100,
  contamination=0.05,   ← assumes 5% of users are anomalous
  random_state=42
)
model.fit(X)
scores = model.score_samples(X)   ← raw anomaly scores per user

for each user:
  risk = _score_to_risk(score)
  upsert AnomalyDetectionResult
```

### 5. Score → Risk Mapping

**File:** `backend/app/crud/ml_anomaly_scorer.py` — `_score_to_risk()`

```
score >= -0.05  → "normal"    is_anomaly=False
score >= -0.10  → "low"       is_anomaly=True
score >= -0.20  → "medium"    is_anomaly=True
score >= -0.30  → "high"      is_anomaly=True
score  < -0.30  → "critical"  is_anomaly=True

Note: IsolationForest scores inliers near 0, outliers near -1.
More negative = more anomalous.
```

### 6. Result Storage

```
AnomalyDetectionResult (DB table: anomalydetectionresult)
  subject_type     → "username"
  subject_value    → the username
  scored_at        → timestamp
  anomaly_score    → raw float from IsolationForest
  is_anomaly       → bool
  risk_level       → "normal" | "low" | "medium" | "high" | "critical"
  feature_snapshot → JSON of the 4 feature values used

Upsert on (subject_type, subject_value) — one row per user, updated daily.
UI: /anomaly_detection
```

---

## Data Sources

| Table | Populated by | Used by |
|---|---|---|
| `authentication_statistics` | TACACS+ auth log parser | alert_evaluator, anomaly_detection |
| `authorization_statistics` | TACACS+ authz log parser | alert_evaluator, anomaly_detection |
| `auditlog` | every API route on CUD operations | alert_evaluator (config check) |
| `alertrule` | user via UI / seeded system rules | alert_evaluator |
| `notificationchannel` | user via UI | alert_evaluator, dispatcher |
| `alertevent` | alert_evaluator on trigger | UI read-only |
| `anomalydetectionresult` | ml_anomaly_scorer daily | UI read-only |

---

## System Alert Rules (seeded on startup)

| Name | log_type | condition | threshold | window | cooldown | severity |
|---|---|---|---|---|---|---|
| High Auth Failure Rate | auth | fail_count gt | 10 | 10 min | 30 min | high |
| New Username Detected | auth | username new_value | — | 60 min | 240 min | medium |
| New Source IP Detected | auth | client_ip new_value | — | 60 min | 240 min | medium |
| High Authorization Deny Rate | authz | deny_count gt | 20 | 10 min | 30 min | high |
| TACACS Config Changed | config | config_action any_change | 1 | 5 min | 5 min | high |
| TACACS Config Activated | config | config_action activated | 1 | 5 min | 5 min | critical |

System rules cannot be deleted (API returns 403). Shown with lock icon in UI.
