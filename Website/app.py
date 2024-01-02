from flask import Flask, redirect, request, jsonify, render_template, url_for
from flask_sqlalchemy import SQLAlchemy
import pandas as pd
import pm4py
from pm4py.objects.conversion.log import converter as log_converter
from pm4py.algo.discovery.dfg import algorithm as dfg_discovery
from pm4py.visualization.dfg import visualizer as dfg_visualization
import os
import datetime
from flask_migrate import Migrate, upgrade


app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
migrate = Migrate(app, db)

class Log(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    case_id = db.Column(db.Integer)
    activity_code = db.Column(db.String(50))
    start_time = db.Column(db.DateTime)
    end_time = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())

data_store = []

with app.app_context():
    db.create_all()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/data')
def data_page():
    return render_template('data.html')

@app.route('/api/data', methods=['GET'])
def get_data():
    logs = Log.query.all()
    data = [{
        'case_id': log.case_id,
        'activity_code': log.activity_code,
        'start_time': log.start_time.isoformat() if log.start_time else None,
        'end_time': log.end_time.isoformat() if log.end_time else None,
        'created_at': log.created_at.isoformat() if log.created_at else None
    } for log in logs]
    return jsonify(data)

@app.route('/api/endpoint', methods=['POST'])
def receive_data():
    data = request.json
    new_log = Log(
        case_id=data['CaseID'],
        activity_code=data['ActivityCode'],
        start_time=datetime.datetime.utcfromtimestamp(data['StartTime'] / 1000.0),
        end_time=datetime.datetime.utcfromtimestamp(data['EndTime'] / 1000.0)
    )
    db.session.add(new_log)
    db.session.commit()
    return jsonify({"status": "success", "data_received": data}), 200


@app.route('/admin/data')
def view_data():
    logs = Log.query.all()
    return render_template('admin_data.html', logs=logs)


@app.route('/generate-dfg', methods=['GET'])
def generate_dfg():
    # Fetch logs from the database and convert to a DataFrame
    query = Log.query.all()
    data = pd.DataFrame([{
        'Case': log.case_id, 
        'ActivityCode': log.activity_code, 
        'Start': log.start_time, 
        'End': log.end_time
    } for log in query])

    if data.empty:
        return redirect(url_for('index', data_empty=True))

    # Ensure that Start and End are in the correct datetime format if they aren't already
    data['Start'] = pd.to_datetime(data['Start'])
    data['End'] = pd.to_datetime(data['End'])

    # Convert DataFrame to an event log
    log_csv = pm4py.format_dataframe(df=data, case_id='Case', activity_key='ActivityCode', timestamp_key='End', start_timestamp_key='Start')
    event_log = log_converter.apply(log_csv)

    # Discover the DFG
    dfg = dfg_discovery.apply(event_log)

    # Visualize the DFG
    gviz = dfg_visualization.apply(dfg, log=event_log)

    # Save the DFG visualization
    path_to_save = os.path.join('static', 'directly_follows_graph.png')
    dfg_visualization.save(gviz, path_to_save)

    return render_template('dfg.html')

if __name__ == '__main__':
    app.run(debug=True)
