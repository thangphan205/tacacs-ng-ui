# Alert Rules & Anomaly Detection — Full Workflow

## Alert Rules

### 1. Rule Storage

```
AlertRule (DB table: alertrule)
  name, description, enabled, is_system
  log_type           → "auth" | "authz" | "config" | "all"
  condition_field    → "fail_count" | "deny_count" | "username" | "client_ip" | "config_action"
  condition_operator → "gt" | "lt" | "eq" | "new_value" | "any_change" | "created" | "updated" | "deleted" | "activated"
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
    for each channel:
      success, err = dispatch_notification(channel, subject, body)
      create AlertEvent(rule_id, channel_id, status, error_message)
    set rule.last_fired_at = now
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
  baseline = DISTINCT username WHERE log_date in [window_start-30d, window_start)
  triggered = (recent - baseline) is not empty

condition_field="client_ip", operator="new_value":
  same as username but on user_source_ip column
```

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

count = COUNT(*) WHERE entity_type="TacacsConfig"
                   AND action IN action_map[operator]
                   AND created_at >= window_start

triggered = count >= threshold
```

### 7. ACTIVATE Audit Log

**File:** `backend/app/api/routes/tacacs_configs.py` — update route

```
old_active = json.loads(old_values)["active"]
if not old_active AND db_tacacs_config.active:
  log_entity_action(action="ACTIVATE", entity_type="TacacsConfig", ...)
```

Written in addition to the standard UPDATE log when a config's `active` field flips `false → true`.

### 8. Notification Dispatch

**File:** `backend/app/crud/notification_dispatcher.py` — `dispatch_notification()`

```
parse channel.config_json → dict

channel_type="telegram":
  POST https://api.telegram.org/bot{token}/sendMessage
  body: { chat_id, text="*{subject}*\n{body}", parse_mode="Markdown" }

channel_type="slack":
  POST webhook_url
  body: { text="*{subject}*\n{body}" }

channel_type="discord":
  POST webhook_url
  body: { content="**{subject}**\n{body}" }

channel_type="teams":
  POST webhook_url
  body: AdaptiveCard JSON with subject + body

channel_type="webhook":
  POST webhook_url
  headers: { Authorization: "Bearer {token}" }  if token present
  body: { subject, body }

returns: (success: bool, error_message: str | None)
timeout: 10 seconds
```

### 9. Alert Event Record

```
AlertEvent (DB table: alertevent)
  rule_id          → FK → AlertRule   (CASCADE delete)
  channel_id       → FK → NotificationChannel (CASCADE delete)
  triggered_at     → timestamp
  payload_snapshot → JSON string (metrics that triggered the rule)
  status           → "sent" | "failed"
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
