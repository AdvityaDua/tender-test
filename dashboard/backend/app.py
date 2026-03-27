from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import psycopg2
from psycopg2.extras import RealDictCursor
import os
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

app = Flask(__name__)
CORS(app)

# Use absolute path for Tenders directory relative to data/
TENDERS_BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../Tenders"))

def get_db_connection():
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        raise ValueError("DATABASE_URL not found in .env file.")
    return psycopg2.connect(database_url, cursor_factory=RealDictCursor)

@app.route('/api/tenders', methods=['GET'])
def get_tenders():
    status = request.args.get('status')
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        if status == 'rejected':
            # Query rejected_tenders table. Alias bid_no to bid_no for consistency.
            cur.execute("SELECT bid_no, keyword, items, start_date, end_date, 'rejected' as status FROM rejected_tenders ORDER BY rejected_at DESC")
        elif status:
            cur.execute("SELECT * FROM tenders WHERE status = %s ORDER BY created_at DESC", (status,))
        else:
            cur.execute("SELECT * FROM tenders ORDER BY created_at DESC")
            
        tenders = cur.fetchall()
        cur.close()
        conn.close()
        return jsonify(tenders)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/tenders/<bid_no>', methods=['GET'])
def get_tender_details(bid_no):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Get tender info - check tenders first
        cur.execute("SELECT * FROM tenders WHERE bid_no = %s", (bid_no,))
        tender = cur.fetchone()
        
        is_from_rejected = False
        if not tender:
            # Check rejected_tenders
            cur.execute("SELECT bid_no, items, start_date, end_date, 'rejected' as status FROM rejected_tenders WHERE bid_no = %s", (bid_no,))
            tender = cur.fetchone()
            is_from_rejected = True
            
        if not tender:
            cur.close()
            conn.close()
            return jsonify({"error": "Tender not found"}), 404
        
        # Get updates/logs (only for standard tenders)
        updates = []
        if not is_from_rejected:
            cur.execute("SELECT * FROM updates WHERE bid_no = %s ORDER BY timestamp DESC", (bid_no,))
            updates = cur.fetchall()
        
        # Get corrigendums (only for standard tenders)
        corrigendums = []
        if not is_from_rejected:
            cur.execute("SELECT * FROM corrigendums WHERE bid_no = %s", (bid_no,))
            corrigendums = cur.fetchall()
        
        cur.close()
        conn.close()

        # Scan filesystem for files
        files = []
        bid_folder_name = bid_no.replace('/', '-')
        
        # Path candidates
        paths = [
            os.path.join(TENDERS_BASE_DIR, bid_folder_name),
            os.path.join(TENDERS_BASE_DIR, "Rejected", bid_folder_name)
        ]
        
        target_path = None
        for p in paths:
            if os.path.exists(p):
                target_path = p
                for f in os.listdir(p):
                    if os.path.isfile(os.path.join(p, f)):
                        files.append(f)
                break
        
        return jsonify({
            **dict(tender),
            "updates": updates,
            "corrigendums": corrigendums,
            "files": files,
            "folder_exists": target_path is not None,
            "is_rejected_source": is_from_rejected
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/tenders/<bid_no>/status', methods=['PATCH'])
def update_tender_status(bid_no):
    data = request.json
    new_status = data.get('status')
    message = data.get('message', f"Status updated to {new_status}")
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Update status
        cur.execute("UPDATE tenders SET status = %s WHERE bid_no = %s", (new_status, bid_no))
        
        # Log update
        cur.execute(
            'INSERT INTO updates (bid_no, status, timestamp, message, "by") VALUES (%s, %s, %s, %s, %s)',
            (bid_no, new_status, datetime.now(), message, 'Manager-Web')
        )
        
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"message": "Status updated successfully"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/files/<path:filename>', methods=['GET'])
def serve_file(filename):
    # filename expected format: bid-no/file.pdf or Rejected/bid-no/file.pdf
    return send_from_directory(TENDERS_BASE_DIR, filename)

if __name__ == '__main__':
    app.run(debug=True, host="0.0.0.0", port=5001)
