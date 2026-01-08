# Quick Deploy via S3 (30 seconds)

## You Already Have Everything You Need!

**Your file:** `nfl-lambda-deployment-supabase.zip` (53.1 MB)  
**Your S3 bucket:** `sportsdatacollection` (already exists!)

---

## Just Run These 2 Commands:

### 1. Upload to S3 (10 seconds):
```bash
aws s3 cp nfl-lambda-deployment-supabase.zip s3://sportsdatacollection/lambda/
```

### 2. Update Lambda (5 seconds):
```bash
aws lambda update-function-code \
  --function-name NFLPredictiveModel \
  --s3-bucket sportsdatacollection \
  --s3-key lambda/nfl-lambda-deployment-supabase.zip
```

**Done!** ✅

---

## OR Via AWS Console (if you prefer clicking):

### Step 1: Upload to S3
1. Go to S3 Console
2. Click bucket: `sportsdatacollection`
3. Create folder: `lambda` (if it doesn't exist)
4. Upload `nfl-lambda-deployment-supabase.zip` to the `lambda/` folder

### Step 2: Update Lambda
1. Go to Lambda Console → NFLPredictiveModel
2. Code tab → "Upload from" dropdown
3. Select **"Amazon S3 location"**
4. Enter: `s3://sportsdatacollection/lambda/nfl-lambda-deployment-supabase.zip`
5. Click Save

**Done!** ✅

---

## Why This Works:

- ✅ No 50 MB limit (S3 upload allows up to 250 MB)
- ✅ Includes psycopg2 (Linux-compatible version)
- ✅ Includes pandas & numpy
- ✅ Includes all your code
- ✅ Uses infrastructure you already have (S3 bucket)

---

## What You're Actually Doing:

You're NOT creating new infrastructure. You're just using S3 as a staging area for your Lambda code. This is the **standard way** to deploy Lambda functions > 50 MB.

It's like saying: "Hey Lambda, instead of me uploading this directly to you, I put it in S3. Go grab it from there."

That's it! 🚀

