from flask import Flask, render_template, request, redirect, url_for
from dotenv import load_dotenv
from simple_salesforce import Salesforce
import xmlrpc.client
import os

app = Flask(__name__)
load_dotenv()

# Initialize Salesforce connection
sf = Salesforce(
    username=os.getenv('SALESFORCE_USERNAME'),
    password=os.getenv('SALESFORCE_PASSWORD'),
    security_token=os.getenv('SALESFORCE_TOKEN'),
    domain='login' if os.getenv('SANDBOX', 'false').lower() == 'true' else None
)

# Odoo connection setup
ODOO_URL = os.getenv('ODOO_URL')
ODOO_DB = os.getenv('ODOO_DB')
ODOO_USER = os.getenv('ODOO_USER')
ODOO_PASSWORD = os.getenv('ODOO_PASSWORD')

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/opportunity', methods=['POST'])
def opportunity():
    try:
        opp_name = request.form['opp_name']
        account_name = request.form['opp_account']
        close_date = request.form['close_date']
        
        # Salesforce: Get Account ID
        account_query = sf.query(f"SELECT Id FROM Account WHERE Name = '{account_name}' LIMIT 1")
        if account_query['totalSize'] == 0:
            return render_template('index.html', 
                message=f"Error: Account {account_name} not found in Salesforce",
                message_class="bg-red-100 text-red-800")
        
        account_id = account_query['records'][0]['Id']
        
        # Create Opportunity in Salesforce
        sf.Opportunity.create({
            'Name': opp_name,
            'AccountId': account_id,
            'CloseDate': close_date,
            'StageName': 'Prospecting'
        })
        
        # Odoo: Get Partner ID
        common = xmlrpc.client.ServerProxy(f'{ODOO_URL}/xmlrpc/2/common')
        uid = common.authenticate(ODOO_DB, ODOO_USER, ODOO_PASSWORD, {})
        models = xmlrpc.client.ServerProxy(f'{ODOO_URL}/xmlrpc/2/object')
        
        partner_id = models.execute_kw(ODOO_DB, uid, ODOO_PASSWORD,
            'res.partner', 'search_read',
            [[['name', '=', account_name]]],
            {'fields': ['id'], 'limit': 1})
        
        if not partner_id:
            return render_template('index.html', 
                message=f"Error: Partner {account_name} not found in Odoo",
                message_class="bg-red-100 text-red-800")
        
        partner_id = partner_id[0]['id']
        
        # Create Opportunity in Odoo
        models.execute_kw(ODOO_DB, uid, ODOO_PASSWORD,
            'crm.lead', 'create',
            [{
                'name': opp_name,
                'partner_id': partner_id,
                'date_deadline': close_date,
                'stage_id': 1  # New stage
            }])
        
        return render_template('index.html', 
            message="Opportunity created successfully in both systems!",
            message_class="bg-green-100 text-green-800")
            
    except Exception as e:
        return render_template('index.html', 
            message=f"Error: {str(e)}", 
            message_class="bg-red-100 text-red-800")

@app.route('/submit', methods=['POST'])
def submit():
    try:
        first_name = request.form['first_name']
        last_name = request.form['last_name']
        account_name = request.form['account_name']
        
        # Salesforce: Create or get Account
        account_query = sf.query(f"SELECT Id FROM Account WHERE Name = '{account_name}' LIMIT 1")
        if account_query['totalSize'] == 0:
            account = sf.Account.create({'Name': account_name})
            account_id = account['id']
        else:
            account_id = account_query['records'][0]['Id']
        
        # Create Contact in Salesforce
        sf.Contact.create({
            'FirstName': first_name,
            'LastName': last_name,
            'AccountId': account_id
        })
        
        # Odoo: Create or get Partner
        common = xmlrpc.client.ServerProxy(f'{ODOO_URL}/xmlrpc/2/common')
        uid = common.authenticate(ODOO_DB, ODOO_USER, ODOO_PASSWORD, {})
        models = xmlrpc.client.ServerProxy(f'{ODOO_URL}/xmlrpc/2/object')
        
        partner_id = models.execute_kw(ODOO_DB, uid, ODOO_PASSWORD,
            'res.partner', 'search_read',
            [[['name', '=', account_name]]],
            {'fields': ['id'], 'limit': 1})
        
        if not partner_id:
            partner_id = models.execute_kw(ODOO_DB, uid, ODOO_PASSWORD,
                'res.partner', 'create',
                [{'name': account_name, 'is_company': True}])
        else:
            partner_id = partner_id[0]['id']
        
        # Create Contact in Odoo
        models.execute_kw(ODOO_DB, uid, ODOO_PASSWORD,
            'res.partner', 'create',
            [{
                'name': f"{first_name} {last_name}",
                'parent_id': partner_id,
                'type': 'contact'
            }])
        
        return render_template('index.html', 
            message="Contact created successfully in both systems!",
            message_class="bg-green-100 text-green-800")
            
    except Exception as e:
        return render_template('index.html', 
            message=f"Error: {str(e)}", 
            message_class="bg-red-100 text-red-800")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)