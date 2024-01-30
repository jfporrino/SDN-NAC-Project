from flask import Flask, request, jsonify, abort
from flask_sqlalchemy import SQLAlchemy
from flask_marshmallow import Marshmallow
import datetime
import socketio

# create a Socket.IO server
sio = socketio.Server(async_mode='threading')

app = Flask(__name__)
app.wsgi_app = socketio.WSGIApp(sio, app.wsgi_app)
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:stong@localhost:3306/NAC-App-DB'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
ma = Marshmallow(app)


class Entry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    mac = db.Column(db.String(17), unique=True)
    current_ip = db.Column(db.String(15))
    is_auth = db.Column(db.Boolean)
    exp = db.Column(db.DateTime)
    user_id = db.Column(db.String(320))
    last_updated = db.Column(db.DateTime)

    def __init__(self, mac, current_ip, is_auth, exp, user_id, last_updated):
        self.mac = mac
        self.current_ip = current_ip
        self.is_auth = is_auth
        self.exp = exp
        self.user_id = user_id
        self.last_updated = last_updated

    def as_dict(self):
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}


with app.app_context():
    db.create_all()


class EntrySchema(ma.Schema):
    class Meta:
        fields = ('id', 'mac', 'current_ip', 'is_auth', 'exp', 'user_id', 'last_updated')


entry_schema = EntrySchema()
entries_schema = EntrySchema(many=True)


@app.route('/isAuth', methods=['Post'])
def is_auth():
    mac = request.json['mac']
    current_ip = request.json['current_ip']
    now = datetime.datetime.now()

    found_entry = Entry.query.filter(Entry.mac == mac).first()
    if found_entry is None:
        exp = now + datetime.timedelta(days=1)
        new_entry = Entry(mac, current_ip, False, exp, '', now)

        db.session.add(new_entry)
        db.session.commit()

        return entry_schema.jsonify(new_entry)

    entry_is_auth = found_entry.is_auth
    entry_exp = found_entry.exp
    entry_is_exp = now > entry_exp

    if entry_is_auth is False:
        found_entry.current_ip = current_ip
        found_entry.last_updated = now

    if entry_is_exp is True:
        found_entry.current_ip = current_ip
        found_entry.last_updated = now
        found_entry.is_auth = False
    else:
        found_entry.current_ip = current_ip
        found_entry.last_updated = now
        found_entry.exp = now + datetime.timedelta(days=1)

    db.session.commit()
    return entry_schema.jsonify(found_entry)


@app.route('/entries', methods=['GET'])
def get_entries():
    all_entries = Entry.query.all()
    result = entries_schema.dump(all_entries)
    return jsonify(result)


@app.route('/auth', methods=['Post'])
def auth():
    current_ip = request.json['current_ip']
    user_id = request.json['user_id']
    now = datetime.datetime.now()

    found_entry = Entry.query.filter(Entry.current_ip == current_ip).first()
    if found_entry is None:
        return abort(404)

    found_entry.user_id = user_id
    found_entry.is_auth = True
    found_entry.exp = now + datetime.timedelta(days=1)
    found_entry.last_updated = now

    db.session.commit()

    sio.emit('update', {'data': {"mac": found_entry.mac, "current_ip": found_entry.current_ip}})
    return entry_schema.jsonify(found_entry)


@app.route('/', methods=['GET'])
def index():
    return jsonify({'message': 'Welcome to my API'})


if __name__ == "__main__":
    app.run()
