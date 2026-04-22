# Claude Handoff: Eastmoney `push2his` Instability

Date: `2026-04-19`
Repo: `D:\Users\rickylu\dev\financial-services-plugins-clean`
Branch: `main`

## 1. Why this handoff exists

Current shortlist / preheat failures are no longer best explained by:

- report logic
- screening logic
- multi-track logic
- cache-fallback wiring bugs

The active blocker is now much narrower:

- Eastmoney realtime quote API (`push2`) is reachable
- Eastmoney historical kline API (`push2his`) is unstable / failing
- the new cache preheat command works structurally, but cannot populate cache
  when `push2his` fails

The user also asked an important product-level question:

> Why did this work normally before, and suddenly stop working now?

This handoff collects the current evidence and the remaining highest-value
investigation path.

## 2. Current user-visible symptom

Two concrete symptoms are currently reproduced locally:

1. `month-end-shortlist` runs can degrade into widespread:
   - `bars_fetch_failed`
   - `top_pick_count = 0`
   - effectively empty `T1` / `T3`

2. The new Eastmoney cache preheat tool:
   - runs correctly
   - prints per-ticker statuses and summary
   - but currently returns only `failed`

Relevant script:

- `D:\Users\rickylu\dev\financial-services-plugins-clean\financial-analysis\skills\month-end-shortlist\scripts\preheat_eastmoney_cache.py`

Relevant test:

- `D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_eastmoney_cache_preheat.py`

Current local verification:

- `8 passed`

## 3. What has already been ruled out

### 3.1 Not a simple repo/code regression

The Eastmoney cache preheat implementation is now on `main` and tested.

The command structure is correct:

- parses tickers from CLI / txt / json
- distinguishes:
  - `cache_hit`
  - `cache_written`
  - `failed`
- prints per-ticker output + summary

The command fails only because upstream Eastmoney kline fetches fail.

### 3.2 Not obviously a public "weekend maintenance" event

We looked for public Eastmoney maintenance announcements and did **not** find a
clear official notice that would explain:

- `push2his` being unavailable this weekend
- while `push2` quote traffic still works

So the current working assumption is:

- **not** a broad public maintenance window
- more likely a selective transport / gateway / compatibility issue

### 3.3 Not purely "TUN mode broke everything"

This was the key mid-run hypothesis, and it is only **partially** true.

Initial evidence:

- local machine had Clash Verge Rev / Mihomo active
- DNS was in `fake-ip` mode
- Eastmoney domains initially resolved to `198.18.x.x`

That proved a proxy/TUN layer was involved.

However, after forcing Eastmoney rules toward `DIRECT` and later disabling TUN,
the core failure still remained:

- `push2his` still failed
- `preheat_eastmoney_cache.py` still failed

So:

- TUN/fake-ip was a confounder
- but **not the whole root cause**

## 4. Current best factual model

### 4.1 `push2` and `push2his` behave differently

Direct probes showed:

- `https://push2.eastmoney.com/api/qt/stock/get?...`
  - returns `200`
  - works under the same environment

- `https://push2his.eastmoney.com/api/qt/stock/kline/get?...`
  - often fails with remote close
  - or with `schannel: server closed abruptly (missing close_notify)`

This is the key split:

- **quote API works**
- **historical kline API fails**

So Eastmoney is not "fully down".

### 4.2 The failure is transport-level, not application-level JSON rejection

Representative errors observed:

- Python / `urllib` path:
  - `Eastmoney request failed: Remote end closed connection without response`

- `curl.exe -v` path:
  - TLS renegotiation occurs
  - then:
    - `schannel: server closed abruptly (missing close_notify)`

This strongly suggests:

- the request is reaching the remote side
- but the HTTPS session is being dropped before a clean response

This is not a normal "HTTP 403" or "maintenance page" pattern.

### 4.3 There was real path churn

At different points in this investigation:

- `push2his.eastmoney.com` resolved to fake-ip addresses such as:
  - `198.18.0.18`
- after `DIRECT` rule changes, it resolved to public addresses such as:
  - `117.184.40.129`
  - later `140.207.67.156`

That means the effective route / DNS path really changed during debugging.

This is relevant to the user's question "why did it work before?"

The answer is likely not one single factor, but some combination of:

- Clash/Mihomo path changed
- generated config regenerated and overwrote temporary edits
- Eastmoney DNS / traffic-manager target changed
- current network exit path changed
- Eastmoney kline gateway behavior changed against this TLS/client path

## 5. Important local environment facts

### 5.1 Clash Verge Rev state

Relevant local appdata root:

- `C:\Users\rickylu\AppData\Roaming\io.github.clash-verge-rev.clash-verge-rev`

Observed config facts:

- `enable_tun_mode: true` at one stage
- `enable_system_proxy: true`
- `dns.enhanced-mode: fake-ip`
- `fake-ip-range: 198.18.0.1/16`

Relevant files inspected:

- `C:\Users\rickylu\AppData\Roaming\io.github.clash-verge-rev.clash-verge-rev\verge.yaml`
- `C:\Users\rickylu\AppData\Roaming\io.github.clash-verge-rev.clash-verge-rev\clash-verge.yaml`
- `C:\Users\rickylu\AppData\Roaming\io.github.clash-verge-rev.clash-verge-rev\profiles.yaml`

### 5.2 Active profile source files matter more than generated runtime YAML

Important discovery:

- editing generated `clash-verge.yaml` is **not durable**
- reload/regeneration can overwrite it

Active profile source files are more durable:

- active rules template:
  - `C:\Users\rickylu\AppData\Roaming\io.github.clash-verge-rev.clash-verge-rev\profiles\rtvoGCBlVBl3.yaml`
- active merge template:
  - `C:\Users\rickylu\AppData\Roaming\io.github.clash-verge-rev.clash-verge-rev\profiles\m7MIBJPSzPqQ.yaml`

The rules template originally looked like:

```yaml
prepend: []
append: []
delete: []
```

I patched this file to add:

```yaml
prepend:
  - DOMAIN,push2his.eastmoney.com,DIRECT
  - DOMAIN,push2.eastmoney.com,DIRECT
```

Backup created:

- `C:\Users\rickylu\AppData\Roaming\io.github.clash-verge-rev.clash-verge-rev\profiles\rtvoGCBlVBl3.yaml.bak.20260419-135735`

This improved the evidence quality because it pushed `push2his` off fake-ip and
back onto public DNS, but it still did **not** make the kline API stable.

### 5.3 TUN disabled test

The user later explicitly disabled TUN mode.

After that:

- `push2his.eastmoney.com` still resolved to a public IP
- `curl` still failed with `missing close_notify`
- preheat still returned `failed`

This is the strongest evidence that:

- the issue is **not only** TUN/fake-ip

## 6. Local repro commands already used

### 6.1 Quote API success

```powershell
curl.exe -v --max-time 20 "https://push2.eastmoney.com/api/qt/stock/get?secid=0.000988&fields=f43,f57,f58,f116,f117,f167,f173"
```

Observed:

- HTTP `200`

### 6.2 Kline API failure

```powershell
curl.exe -v --max-time 20 "https://push2his.eastmoney.com/api/qt/stock/kline/get?fields1=f1,f2,f3,f4,f5,f6&fields2=f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61&klt=101&fqt=0&lmt=2&ut=fa5fd1943c7b386f172d6893dbfba10b&secid=0.000988&beg=20260417&end=20260419"
```

Observed repeatedly:

- TLS renegotiation
- abrupt close
- `curl: (56) schannel: server closed abruptly (missing close_notify)`

### 6.3 Python preheat smoke

```powershell
& "C:\Users\rickylu\AppData\Local\Programs\Python\Launcher\py.exe" `
  "D:\Users\rickylu\dev\financial-services-plugins-clean\financial-analysis\skills\month-end-shortlist\scripts\preheat_eastmoney_cache.py" `
  --tickers 000988.SZ,002384.SZ,300476.SZ
```

Observed:

```text
[failed] 000988.SZ - Eastmoney request failed: Remote end closed connection without response
[failed] 002384.SZ - Eastmoney request failed: Remote end closed connection without response
[failed] 300476.SZ - Eastmoney request failed: Remote end closed connection without response
Summary:
- total: 3
- cache_hit: 0
- cache_written: 0
- failed: 3
```

## 7. Best answer to "why did it work before, then suddenly stop?"

I do **not** think there is one fully-proven single cause yet.

The most credible explanation is a combination of **path drift** and
**endpoint sensitivity**:

1. The machine/network path to Eastmoney changed over time
   - Mihomo fake-ip / direct routing state changed
   - generated config could overwrite temporary fixes
   - Eastmoney DNS target also changed during probing

2. `push2his` is materially more fragile than `push2`
   - quote keeps working
   - historical kline does not

3. Something about the **current client/transport path** is now incompatible
   with `push2his`
   - current network exit
   - current TLS stack (`schannel`)
   - Eastmoney gateway behavior
   - or some combination of those

So the current best human-language answer is:

> It likely worked before because the effective network path/client behavior to
> `push2his` used to be different enough to pass. Now that path has drifted
> (proxy/direct/DNS target/TLS behavior), and the Eastmoney historical kline
> endpoint is selectively rejecting or aborting it.

## 8. Highest-value next steps for Claude

### 8.1 Separate network-exit cause from Windows TLS-stack cause

This is the highest-value branch to continue.

Recommended next tests:

1. **Different network exit**
   - mobile hotspot
   - same `curl` kline probe

2. **Different TLS/client stack on same machine**
   - WSL `curl`
   - OpenSSL-based Python requests/httpx session
   - or browser devtools/XHR if convenient

If:

- hotspot works
  - then current ISP / current network path is strongly suspect

- WSL/OpenSSL works but Windows `schannel` fails
  - then Windows TLS stack / current client path is strongly suspect

### 8.2 Check whether Eastmoney kline is sensitive to HTTP protocol/client specifics

Suggested:

- compare `curl.exe` (schannel) vs WSL curl
- compare Python `urllib` vs `requests` / `httpx`
- test small query windows vs larger windows, but only after client stack is isolated

### 8.3 Only after transport cause is isolated, decide whether shortlist should change

Do **not** redesign shortlist logic yet.

Current blocker remains transport / market-data ingress, not screening policy.

## 9. What not to waste time on next

- Do not keep editing generated `clash-verge.yaml` as the main fix path
  - it gets regenerated

- Do not assume TUN is the sole cause
  - TUN off still failed

- Do not assume Eastmoney public maintenance without stronger evidence
  - quote API is still live

- Do not keep retrying the same Python preheat command without changing network
  exit or TLS client path
  - it currently adds little new information

## 10. Useful local files touched or created during this investigation

### Repo files

- `D:\Users\rickylu\dev\financial-services-plugins-clean\financial-analysis\skills\month-end-shortlist\scripts\preheat_eastmoney_cache.py`
- `D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_eastmoney_cache_preheat.py`

### Local non-repo config files

- `C:\Users\rickylu\AppData\Roaming\io.github.clash-verge-rev.clash-verge-rev\profiles\rtvoGCBlVBl3.yaml`
- `C:\Users\rickylu\AppData\Roaming\io.github.clash-verge-rev.clash-verge-rev\profiles\rtvoGCBlVBl3.yaml.bak.20260419-135735`

Earlier temporary edits / backups were also made to generated Clash YAML files,
but those are lower-value now than the active profile source file above.
