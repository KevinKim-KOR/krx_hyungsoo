---
description: "Deploy code changes to OCI: Commit -> Push -> Pull"
---

1. **Update Documentation**:
   - Update `task.md` (Checklist)
   - Update `walkthrough.md` (Technical Details)

2. **Commit Local Changes**:
   ```bash
   git add .
   git commit -m "Deploy: {message}"
   ```

2. **Push to Remote**:
   ```bash
   // turbo
   git push origin main
   ```

3. **Pull on OCI**:
   ```bash
   // turbo
   ssh -i "oracle_cloud_key" ubuntu@168.107.51.68 "git -C krx_hyungsoo pull"
   ```

4. **Verify**:
   - Check `git log -1` on OCI.
