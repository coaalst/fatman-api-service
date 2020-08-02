from flask import request, jsonify, make_response
from app import app

import jwt, datetime, uuid, zmq
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps

# Models
from app.models import User
from app.models import Entry

# DB
from app import db

# ZMQ setup
context = zmq.Context()
socket = context.socket(zmq.REQ)
socket.connect(Config.web_controller_conn_str)

# Token auth verification function
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        if 'x-access-token' in request.headers:
            token = request.headers['x-access-token']

        if not token:
            return jsonify({'message' : 'Token not found!'}), 401

        try:
            data = jwt.decode(token, app.config['SECRET_KEY'])
            current_user = User.query.filter_by(username = data['public']).first
        except:
            return jsonify({'message' : 'Token is invalid!'}), 401

        return f(current_user, *args, **kwargs)

    return decorated

@app.route('/')
@token_required
def entry_bundle(current_user):

    bundle = Entry.query.all()  
    return jsonify(bundle), 200

@app.route('/update', methods=['POST'])
@token_required
def update_config(current_user):

    status = {
        "temp" : "0.0",
        "tempUnits" : "C",
        "humidity" : "0.0",
        "elapsed" : "0",
        "mode" : "off",
        "fan_state" : "on",
        "light_state" : "on",
        "pump_state" : "off",
    }

    status["mode"] = request.form["mode"]
    status["temp"] = float(request.form["temp"])
    status["tempUnits"] = float(request.form["tempUnits"])
    status["humidity"] = float(request.form["humidity"])
    status["elapsed"] = float(request.form["elapsed"]) 
    status["fan_state"] = request.form["fan_state"] 
    status["light_state"] = request.form["light_state"]
    status["pump_state"] = request.form["pump_state"]

    socket.send(status)
    return jsonify({'message' : 'Config updated!'}), 200

@app.route('/login', methods=['GET'])
def login():

    auth = request.authorization
    if not auth or not auth.username or not auth.password:
        return make_response('Error', 401, {'WWW-Authenticate' : 'Basic realm="Login required!"'})

    user = User.query.filter_by(username = auth.username).first()

    if not user:
       return make_response('Error, user not found', 401, {'WWW-Authenticate' : 'Basic realm="User not found!"'}) 

    if check_password_hash(user.password, auth.password):
        token = jwt.encode({'public' : user.username, 'exp' : datetime.datetime.utcnow() + datetime.timedelta(minutes = 30)}, app.config['SECRET_KEY'])
        return jsonify({'token' : token.decode('UTF-8')})

    return make_response('Error, user not found', 401, {'WWW-Authenticate' : 'Basic realm="Login failed!"'})

@app.route('/user', methods=['POST'])
def create_user():
    data = request.get_json()

    hashed_password = generate_password_hash(data['password'], method='sha256')

    new_user = User(username=data['username'], password=hashed_password)
    db.session.add(new_user)
    db.session.commit()

    return jsonify({'message' : 'New user created!'}), 201
