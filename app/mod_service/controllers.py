from flask import Blueprint, jsonify, request, session
from sqlalchemy.exc import SQLAlchemyError
from logging import getLogger
from ..mod_auth import require_auth
from ..mod_db import db
from .models import Service
from ..mod_check import MySQL, FTP, SSH, IMAP, SMTP, SMB

mod_service = Blueprint('service', __name__, url_prefix='/api/data/service')
logger = getLogger(__name__)


@mod_service.route('/create', methods=['POST'])
@require_auth
def create_service():
    return_code = 401

    # for now, only admins should be able to create new services
    if session.get('_admin', False):
        service_params = [request.form.get(k) for k in ['name', 'host', 'port', 'type', 'team_id']]

        # check that all the necessary params have been provided and contain a value
        if all(service_params):
            # expand out into variables
            name, host, port, service_type, team_id = service_params
            # team_id = None

            # !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
            # if teams should be able to make their own services,
            # uncomment this and remove the first check
            # !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

            # if an admin, get the service team ID from the body parameters
            # if session.get('_admin', False):
            #     team_id = request.form.get('team')
            # else:
            #     # if there's a team session cookie, get that as the team ID
            #     if '_team' in session:
            #         team_id = session['_team']
            #     else:
            #         logger.error('No team session cookie')

            # check that the team ID has been retrieved
            if team_id is not None:
                # try to add it into the DB
                try:
                    service = Service(name=name,
                                      host=host,
                                      port=int(port),
                                      service_type=service_type,
                                      team_id=int(team_id))
                    db.session.add(service)
                    db.session.commit()

                    return jsonify({'success': True, 'id': service.id})
                except (SQLAlchemyError, TypeError) as e:
                    logger.exception(e)
                    # catch TypeError in case the int conversion fails
                    db.session.rollback()
                    pass
            else:
                logger.error('No team ID')

            return_code = 400

    return jsonify({'success': False}), return_code


@mod_service.route('/remove', methods=['POST'])
@require_auth
def remove_service():
    return_code = 401
    # only an admin should be able to remove a service
    if session.get('_admin', False):
        # if the service ID was provided
        service_id = request.form.get('service_id')
        if service_id is not None:
            try:
                service = Service.query.filter(Service.id == service_id).first()
                if service is not None:
                    db.session.delete(service)
                    db.session.commit()

                    return jsonify({'success': True}), 200
            except SQLAlchemyError as e:
                logger.exception(e)
                db.session.rollback()

        # return a 400 Bad Request if something went wrong
        return_code = 400

    return jsonify({'success': False}), return_code


@mod_service.route('/update', methods=['POST'])
@require_auth
def update_service():
    return_code = 400

    # check if service ID and possible properties were given
    service_id = request.form.get('service_id')
    available_keys = [request.form.get(k) for k in ['name', 'host', 'port', 'type']]
    if service_id is not None and any(available_keys):
        name, host, port, service_type = available_keys

        # check that the service exists
        service = Service.query.filter(Service.id == service_id).first()
        if service is not None:
            success = True
            team_id = None
            is_admin = session.get('_admin', False)
            # get the team ID
            if '_team' in session:
                team_id = session['_team']

            # check if admin or logged in
            if is_admin or (team_id is not None and service.team_id == team_id):
                # update the name if provided
                if name is not None:
                    service.name = name

                # update the host if provided (admin-only)
                if host is not None:
                    if is_admin:
                        service.host = host
                    else:
                        logger.error('Non-admin failed to update service host')
                        success = False

                # update the port if provided
                if port is not None:
                    # catch exception if port is not a valid int
                    try:
                        service.port = int(port)
                    except ValueError:
                        pass

                # update the service type if provided (admin-only)
                if service_type is not None:
                    if is_admin:
                        service.service_type = service_type
                    else:
                        logger.error('Non-admin failed to update service type')
                        success = False

                if success:
                    db.session.commit()
                    return jsonify({'success': True}), 200
            else:
                logger.error('Team ID mismatch or not admin!')
                return_code = 401

    return jsonify({'success': False}), return_code


@mod_service.route('/list', methods=['GET', 'POST'])
@require_auth
def list_services():
    services = None
    if session.get('_admin', False):
        services = Service.query.all()
    elif '_team' in session:
        services = Service.query.filter(Service.team_id == session['_team']).all()
    else:
        logger.error('No team or admin cookies!?')

    if services is not None:
        return jsonify({
            'services': [{
                'id': s.id,
                'name': s.name,
                'host': s.host,
                'port': s.port,
                'type': s.service_type
            } for s in services]
        })

    return jsonify({'success': False}), 400


def mysql_check(service, username, password, db_name):
    return MySQL.check.delay(host=service.host,
                             port=service.port,
                             username=username,
                             password=password,
                             db=db_name)


def ftp_check(service, username, password):
    return FTP.check.delay(host=service.host,
                           port=service.port,
                           username=username,
                           password=password)


def ssh_check(service, username, password):
    return SSH.check.delay(host=service.host,
                           port=service.port,
                           username=username,
                           password=password)


def imap_check(service, username, password, use_ssl):
    return IMAP.check.delay(host=service.host,
                            port=service.port,
                            username=username,
                            password=password,
                            use_ssl=(use_ssl.lower() == 'true'))


def smtp_check(service, username, password, domain, use_ssl):
    return SMTP.check.delay(host=service.host,
                            port=service.port,
                            username=username,
                            password=password,
                            domain=domain,
                            use_ssl=(use_ssl.lower() == 'true'))


def smb_check(service, username, password, remote_name):
    return SMB.check.delay(host=service.host,
                           port=service.port,
                           username=username,
                           password=password,
                           remote_name=remote_name)


service_list = {
    'MySQL': (mysql_check, ('username', 'password', 'db_name')),
    'FTP': (ftp_check, ('username', 'password')),
    'SSH': (ssh_check, ('username', 'password')),
    'IMAP': (imap_check, ('username', 'password', 'use_ssl')),
    'SMTP': (smtp_check, ('username', 'password', 'domain', 'use_ssl')),
    'SMB': (smb_check, ('username', 'password', 'remote_name'))
}


@mod_service.route('/check', methods=['POST'])
@require_auth
def check_service():
    return_code = 401

    # only admins can manually check a service by ID
    if session.get('_admin', False):
        # get service ID if provided
        service_id = request.form.get('service_id')
        if service_id is not None:
            # get the service from the DB
            service = Service.query.filter(Service.id == service_id).first()
            if service is not None:
                service_type = service.service_type

                # check if the service type is in the list
                if service_type in service_list:
                    # get the check handling method and the name of the form args to check for
                    check_method, arg_names = service_list[service_type]

                    # get form args and check that they all have been set
                    body_args = [request.form.get(k) for k in arg_names]
                    if all(body_args):
                        # if so, call the check method with the service object and kwargs made from the parameters
                        res = check_method(service, **dict(zip(arg_names, body_args)))
                        res_val = res.get(timeout=10)

                        return jsonify({
                            'success': all(res_val is not x for x in [None, False]),
                            'result': res_val
                        }), 200
                    else:
                        logger.error('Missing body arguments: %s', ', '.join(set(arg_names) - set(request.form)))
                else:
                    # if not in the list, return an error
                    logger.error('Service %s not implemented', service_type)
                    return jsonify({'success': False, 'error': 'service_not_implemented'}), 400
            else:
                logger.error('Service ID not found in database')
        else:
            logger.error('Service ID not provided')

        return_code = 400

    return jsonify({'success': False}), return_code
