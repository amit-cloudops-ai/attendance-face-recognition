# Demo Video Storyboard (target 6 to 8 minutes)

Record on the **prod** environment with real team members. Screen + webcam, one take per scene, trim after.

| # | Scene | Show | Say (key point) |
|---|---|---|---|
| 1 | Intro (30 s) | Architecture diagram | Problem, serverless approach, flow in one sentence |
| 2 | Face registration (90 s) | Admin login, Add employee, consent checkbox, capture 4 photos, "enrolled" on each | Rekognition indexes the face; photos are deleted right after |
| 3 | Clock-in (60 s) | Kiosk: live preview, capture, result with name, time, status (stopwatch visible) | Under 3 s; status present/late by shift + grace |
| 4 | Evidence (45 s) | S3 raw bucket `captures/` empty; DynamoDB attendance item | No biometric images stored |
| 5 | Duplicate scan (20 s) | Scan again immediately | "Already clocked in" (debounce) |
| 6 | Clock-out (45 s) | Lower `debounce_minutes` to 1 in Settings beforehand, scan again after 1 min | Clock-out updated, last scan wins |
| 7 | Unknown person (30 s) | Someone not enrolled scans | `no_match`, nothing written |
| 8 | Admin summary (90 s) | Filter by employee, date range, status; export CSV; open daily and weekly report | Analytics: present %, late %, absences |
| 9 | Automation (60 s) | Run daily-job manually in Lambda console; show absent rows and the file in the reports bucket | Scheduler runs this at 23:59 IST |
| 10 | Security and ops (60 s) | IAM role of `recognize`, S3 lifecycle + encryption, CloudWatch alarm, CI pipeline run, cost sheet | Least privilege, IaC, observability |
| 11 | Close (15 s) | README | Known limitation: liveness planned |
