activate_this = '/opt/flask/env/bin/activate'
with open(activate_this) as file_:
    exec(file_.read(), dict(__file__=activate_this))

import sys
sys.path.insert(0, '/opt/flask')

import app as application
