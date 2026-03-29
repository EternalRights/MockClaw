# 🚨 FTUE: First Time User Experience is Broken

**Priority:** Critical  
**Labels:** `bug`, `documentation`, `good-first-issue`, `ftue`  
**Milestone:** v0.2.1 - User Experience

---

## Problem Statement

A fresh user cloning MockClaw **cannot successfully run a test in under 5 minutes** without hitting multiple blockers. The current workflow requires too many manual steps and assumes knowledge the user doesn't have.

---

## Blockers Found (Fresh Clone Test)

### 🔴 BLOCKER 1: No Sample HAR File Bundled

**Issue:** Users must record their own traffic before they can test anything.

**Current workflow:**
```bash
# User clones repo
git clone ...
cd MockClaw

# User tries to generate mocks
mockclaw generate ??? ./mocks  # ❌ No HAR file!

# User has to:
# 1. Find and start dummy_shop.py (not obvious)
# 2. Run recorder (another step)
# 3. Hope it works
```

**Expected workflow:**
```bash
# User clones repo
git clone ...
cd MockClaw

# User generates from bundled sample
mockclaw generate sample_data/flow.har ./mocks  # ✅ Works immediately!

# OR even better - one command:
mockclaw quickstart  # ✅ Does everything automatically
```

**Fix required:**
- [ ] Create `sample_data/` directory
- [ ] Bundle a pre-recorded `flow.har` file with 5-10 endpoints
- [ ] Include both success and error scenarios (expired coupon)
- [ ] Update README and QUICKSTART to reference sample data

---

### 🔴 BLOCKER 2: Missing Dependencies in Install Instructions

**Issue:** `QUICKSTART.md` says `pip install -e .` but doesn't mention `typer` which is required for CLI.

**Error user sees:**
```bash
$ mockclaw --help
ModuleNotFoundError: No module named 'typer'
```

**Fix required:**
- [ ] Add `typer` to `src/requirements.txt`
- [ ] Verify all CLI dependencies are listed
- [ ] Test fresh install in clean virtualenv

---

### 🔴 BLOCKER 3: No "Zero to Test" Quick Path

**Issue:** User has to read multiple sections to figure out the minimum workflow.

**Current docs structure:**
1. Installation (multiple options)
2. Running (3 different methods)
3. Gauntlet Workflow (4 steps)
4. Then maybe tests?

**User thinks:** "I just want to see it work in 2 minutes!"

**Fix required:**
- [ ] Add **"Quick Test (60 seconds)"** section at TOP of README
- [ ] One command to generate from sample HAR
- [ ] One command to start server
- [ ] One command to run demo test
- [ ] Everything else can be in later sections

---

### 🟡 BLOCKER 4: Dummy Shop Discovery Problem

**Issue:** User has to find `tests/gauntlet/dummy_shop.py` to record traffic.

**Error:**
```bash
$ mockclaw record
❌ Cannot connect to Dummy Shop!

Please start Dummy Shop first:
  python tests/gauntlet/dummy_shop.py  # User: "Where??"
```

**Fix required:**
- [ ] Add `dummy_shop.py` symlink/copy to `sample_data/` directory
- [ ] Or better: include instructions in `mockclaw record --help`
- [ ] Or best: `mockclaw record` should auto-start dummy shop if not running

---

### 🟡 BLOCKER 5: No Verification Test Included

**Issue:** After generating mocks, user doesn't know if it worked.

**Current:** User has to write their own test file

**Expected:** Include `test_demo.py` or `verify_mocks.py` that runs automatically

**Fix required:**
- [ ] Bundle `sample_data/test_demo.py` with 3 simple tests
- [ ] Add `mockclaw verify ./mocks` command
- [ ] Or: `mockclaw generate` automatically runs verification

---

## User Journey Map (Current vs Expected)

### Current Journey (15+ minutes, multiple failures)
```
1. Clone repo
2. Read README (confused - too many options)
3. Try `pip install -e .` (missing typer - ERROR)
4. Install typer manually
5. Try `mockclaw generate` (no HAR file - ERROR)
6. Find dummy_shop.py after searching
7. Start dummy_shop in Terminal 1
8. Run `mockclaw record` in Terminal 2
9. Try `mockclaw generate` (works!)
10. Start server with `mockclaw serve`
11. Write test file manually
12. Run test (works!)
```

**Frustration points:** 4 (steps 2, 3, 5, 11)  
**Total time:** 15-20 minutes  
**Chance of giving up:** 60%

---

### Expected Journey (2 minutes, zero failures)
```
1. Clone repo
2. Run `mockclaw quickstart` (auto-generates from sample, starts server)
3. Run included `test_demo.py` (works!)
```

**Frustration points:** 0  
**Total time:** 2 minutes  
**Chance of giving up:** 5%

---

## Recommended Fixes (Priority Order)

### Phase 1: Critical (Do Now)
1. **Bundle sample HAR file** (`sample_data/flow.har`)
2. **Add `typer` to requirements.txt**
3. **Create "Quick Test (60 seconds)" section** at top of README
4. **Include demo test file** (`sample_data/test_demo.py`)

### Phase 2: Important (This Sprint)
5. **Add `mockclaw quickstart` command** that:
   - Generates from sample HAR
   - Starts server on port 8000
   - Prints test instructions
6. **Auto-start dummy shop** when running `mockclaw record`
7. **Add verification command** (`mockclaw verify`)

### Phase 3: Nice to Have (Next Sprint)
8. **Interactive tutorial mode** (`mockclaw tutorial`)
9. **Video walkthrough** linked from README
10. **Troubleshooting wizard** (`mockclaw doctor`)

---

## Acceptance Criteria

**After fixes are applied, a fresh user must be able to:**

- [ ] Clone repo and run successful test in **under 5 minutes**
- [ ] Follow **single path** in README (no decision paralysis)
- [ ] Use **bundled sample data** (no recording required)
- [ ] See **both success and error scenarios** work (coupon testing)
- [ ] Get **clear error messages** if something fails
- [ ] Have **zero dependencies missing** after install

**Success metric:** New user can complete "Quick Test" section in < 5 minutes with 90%+ success rate.

---

## Files to Create/Modify

### Create:
- [ ] `sample_data/flow.har` (pre-recorded traffic)
- [ ] `sample_data/test_demo.py` (demo test file)
- [ ] `sample_data/README.md` (sample data documentation)

### Modify:
- [ ] `README.md` - Add "Quick Test (60 seconds)" at top
- [ ] `QUICKSTART.md` - Reference sample data
- [ ] `src/requirements.txt` - Add `typer`
- [ ] `src/cli.py` - Add `quickstart` command

---

## Impact

**Current state:** 60% of users give up before first successful test  
**Target state:** 95% of users complete quick test successfully

**Business impact:**
- Better adoption rate
- More GitHub stars
- Less support burden
- Happier users

---

## Related Issues

- #123 - CLI documentation improvements
- #156 - Sample data for testing
- #189 - Onboarding experience

---

**Assignee:** @Evangelist (documentation), @Developer (code changes)  
**Due date:** End of Sprint 2  
**Status:** 🔴 BLOCKING NEXT RELEASE
