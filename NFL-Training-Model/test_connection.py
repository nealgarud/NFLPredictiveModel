"""
Quick test script to verify database connection and data availability
Run this before executing prepare_training_data.py
"""

import sys
import os

# Add parent directory to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'PredictiveDataModel', 'DataIngestionLambda'))

try:
    from DatabaseConnection import DatabaseConnection
    print("✅ Successfully imported DatabaseConnection")
except ImportError as e:
    print(f"❌ Failed to import DatabaseConnection: {e}")
    print("\nMake sure the path to DatabaseConnection.py is correct.")
    sys.exit(1)

def test_connection():
    """Test database connection and query basic data"""
    print("\n" + "="*60)
    print("🔍 Testing NFL Training Model Database Connection")
    print("="*60)
    
    try:
        # Test 1: Connection
        print("\n1️⃣ Testing database connection...")
        db = DatabaseConnection()
        conn = db.get_connection()
        print("   ✅ Connection established")
        
        # Test 2: Query games count
        print("\n2️⃣ Checking available games...")
        query = """
        SELECT 
            season,
            COUNT(*) as game_count
        FROM games
        WHERE game_type = 'REG'
            AND home_score IS NOT NULL
            AND spread_line IS NOT NULL
        GROUP BY season
        ORDER BY season DESC
        """
        
        result = conn.run(query)
        
        if result:
            print("   ✅ Games found:")
            total_games = 0
            for row in result:
                season, count = row
                print(f"      Season {season}: {count} games")
                total_games += count
            print(f"      Total: {total_games} games")
            
            if total_games < 50:
                print("\n   ⚠️  Warning: Less than 50 games available. Training data may be limited.")
        else:
            print("   ❌ No games found in database")
            return False
        
        # Test 3: Check required columns
        print("\n3️⃣ Verifying required columns...")
        test_query = """
        SELECT 
            game_id,
            season,
            week,
            gameday,
            home_team,
            away_team,
            home_score,
            away_score,
            spread_line,
            div_game
        FROM games
        WHERE season = 2024
            AND game_type = 'REG'
            AND home_score IS NOT NULL
        LIMIT 1
        """
        
        test_result = conn.run(test_query)
        
        if test_result:
            print("   ✅ All required columns present")
            sample = test_result[0]
            print(f"      Sample game: {sample[4]} vs {sample[5]} (Week {sample[2]}, {sample[1]})")
        else:
            print("   ❌ Failed to query required columns")
            return False
        
        # Test 4: Check teams
        print("\n4️⃣ Checking team data...")
        teams_query = """
        SELECT DISTINCT home_team 
        FROM games 
        WHERE season = 2024 
        ORDER BY home_team
        """
        
        teams_result = conn.run(teams_query)
        
        if teams_result:
            team_count = len(teams_result)
            print(f"   ✅ Found {team_count} teams")
            if team_count == 32:
                print("      Perfect! All 32 NFL teams present")
            else:
                print(f"      ⚠️  Expected 32 teams, found {team_count}")
        
        # Test 5: Environment check
        print("\n5️⃣ Checking environment configuration...")
        env_vars = [
            'SUPABASE_DB_HOST',
            'SUPABASE_DB_PASSWORD',
            'SUPABASE_DB_NAME',
            'SUPABASE_DB_USER',
            'SUPABASE_DB_PORT'
        ]
        
        missing = []
        for var in env_vars:
            if not os.environ.get(var):
                missing.append(var)
        
        if missing:
            print(f"   ⚠️  Missing environment variables: {', '.join(missing)}")
            print("      Make sure to set these before running prepare_training_data.py")
        else:
            print("   ✅ All environment variables set")
        
        # Success summary
        print("\n" + "="*60)
        print("✅ All checks passed! Ready to generate training data.")
        print("="*60)
        print("\nNext step:")
        print("  python prepare_training_data.py")
        print()
        
        return True
        
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        import traceback
        print("\nFull traceback:")
        print(traceback.format_exc())
        
        print("\n" + "="*60)
        print("Troubleshooting tips:")
        print("="*60)
        print("1. Check your .env file has correct Supabase credentials")
        print("2. Verify your database connection (try connecting with psql)")
        print("3. Ensure the games table exists and has data")
        print("4. Check network connectivity to Supabase")
        print()
        
        return False


if __name__ == "__main__":
    success = test_connection()
    sys.exit(0 if success else 1)

