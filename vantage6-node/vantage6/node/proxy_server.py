"""
This module contains a proxy server implementation that the node uses to
communicate with the server. It contains general methods for any routes, and
methods to handle tasks and results, including their encryption and decryption.

(!) Not to be confused with the squid proxy that allows algorithm containers
to access other places in the network.
"""
import requests
import logging

from http import HTTPStatus
from requests import Response

from flask import Flask, request, jsonify

from vantage6.common import bytes_to_base64s, base64s_to_bytes, logger_name
from vantage6.common.client.node_client import NodeClient

# Initialize FLASK
app = Flask(__name__)
log = logging.getLogger(logger_name(__name__))

# Need to be set when the proxy server is initialized
app.config["SERVER_IO"] = None
server_url = None

# Number of times the request is retried before the proxy server gives up
RETRY = 3


def get_method(method: str) -> callable:
    """
    Obtain http method based on string identifier

    Parameters
    ----------
    method : str
        Http method requested

    Returns
    -------
    function
        HTTP method
    """
    method_name: str = method.lower()

    loopup = {
        "get": requests.get,
        "post": requests.post,
        "patch": requests.patch,
        "put": requests.put,
        "delete": requests.delete
    }

    return loopup.get(method_name, requests.get)


def make_proxied_request(endpoint: str) -> Response:
    """
    Helper to create proxies requests to the central server.

    Parameters
    ----------
    endpoint: str
        endpoint to be reached at the vantage6 server

    Returns
    -------
    requests.Response
        Response from the vantage6 server
    """
    present = 'Authorization' in request.headers
    headers = {'Authorization': request.headers['Authorization']} if present \
        else None

    json = request.get_json() if request.is_json else None
    return make_request(request.method, endpoint, json, request.args, headers)


def make_request(method: str, endpoint: str, json: dict = None,
                 params: dict = None, headers: dict = None) -> Response:
    """
    Make request to the central server

    Parameters
    ----------
    method: str
        HTTP method to be used
    endpoint: str
        endpoint of the vantage6 server
    json: dict, optional
        JSON body
    params: dict, optional
        HTTP parameters
    headers: dict, optional
        HTTP headers

    Returns
    -------
    requests.Response
        Response from the vantage6 server
    """

    method = get_method(method)

    # Forward the request to the central server. Retry when an exception is
    # raised (e.g. timeout or connection error) or when the server gives an
    # error code greater than 210
    url = f"{server_url}/{endpoint}"
    for i in range(RETRY):
        try:
            response: Response = method(url, json=json,
                                        params=params,
                                        headers=headers)
            # verify that the server gave us a valid response, else we
            # would want to try again
            if response.status_code > 210:
                log.warn('Proxy server received status code:'
                         f'{response.status_code}')
                log.debug(f'method: {request.method}, url: {url}, json: {json}'
                          f', params: {params}, headers: {headers}')
                if 'application/json' in response.headers.get('Content-Type'):
                    log.debug(response.json().get("msg", "no description..."))

            else:
                # Exit the retry loop because we have collected a valid
                # response
                return response

        except Exception:
            log.exception(f'On attempt {i}, the proxy request raised an '
                          f'exception: <{url}>')

    # if all attemps fail, raise an exception to be handled by its parent
    raise Exception("Proxy request failed")


def decrypt_result(run: dict) -> dict:
    """
    Decrypt the `result` from a run dictonary

    Parameters
    ----------
    run: dict
        Run dict

    Returns
    -------
    dict
        Run dict with the `result` decrypted
    """
    client: NodeClient = app.config.get('SERVER_IO')

    # if the result is a None, there is no need to decrypt that..
    try:
        if run['result']:
            run["result"] = bytes_to_base64s(
                client.cryptor.decrypt_str_to_bytes(
                    run["result"]
                )
            )
    except Exception:
        log.exception("Unable to decrypt and/or decode results, sending them "
                      "to the algorithm...")

    return run


def get_response_json_and_handle_exceptions(
        response: Response) -> dict | None:
    """
    Obtain json content from request response

    Parameters
    ----------
    response : requests.Response
        Requests response object

    Returns
    -------
    dict | None
        Dict containing the json body
    """
    try:
        return response.json()
    except (requests.exceptions.JSONDecodeError, Exception):
        log.exception('Failed to extract JSON')
    return None


@app.route("/task", methods=["POST"])
def proxy_task():
    """
    Proxy to create tasks at the vantage6 server

    Returns
    -------
    requests.Response
        Response from the vantage6 server
    """
    # We need the server io for the decryption of the results
    client: NodeClient = app.config.get("SERVER_IO")
    if not client:
        log.error("Task proxy request received but proxy server was not "
                  "initialized properly.")
        return jsonify({'msg': 'Proxy server not initialized properly'}), 500

    # All requests from algorithms are unencrypted. We encrypt the input
    # field for a specific organization(s) specified by the algorithm
    data = request.get_json()
    organizations = data.get("organizations")

    if not organizations:
        log.error("No organizations found in proxy request..")
        return jsonify({"msg": "Organizations missing from input"}), 400

    try:
        headers = {'Authorization': request.headers['Authorization']}
    except Exception:
        log.exception('Could not extract headers from request...')

    log.debug(f"{len(organizations)} organizations")

    # For every organization we need to encrypt the input field. This is done
    # in parallel as the client (algorithm) is waiting for a timely response.
    # For every organizationn the public key is retrieved an the input is
    # encrypted specifically for them.
    def encrypt_input(organization: dict) -> dict:
        """
        Encrypt the input for a specific organization by using its private key.
        This method is run as background

        Parameters
        ----------
        organization : dict
            Input as specified by the client (algorithm in this case)

        Returns
        -------
        dict
            Modified organization dictionary in which the `input` key is
            contains encrypted input
        """
        input_ = organization.get("input", {})
        organization_id = organization.get("id")

        # retrieve public key of the organization
        log.debug(f"Retrieving public key of org: {organization_id}")
        response = make_request('get', f'organization/{organization_id}',
                                headers=headers)
        public_key = response.json().get("public_key")

        # Encrypt the input field
        client: NodeClient = app.config.get("SERVER_IO")
        organization["input"] = client.cryptor.encrypt_bytes_to_str(
            base64s_to_bytes(input_),
            public_key
        )

        log.debug("Input succesfully encrypted for organization "
                  f"{organization_id}!")
        return organization

    if client.is_encrypted_collaboration():

        log.debug("Applying end-to-end encryption")
        data["organizations"] = [encrypt_input(o) for o in organizations]

    # Attempt to send the task to the central server
    try:
        response = make_request('post', 'task', data, headers=headers)
    except Exception:
        log.exception('post task failed')
        return {'msg': 'Request failed, see node logs'},\
            HTTPStatus.INTERNAL_SERVER_ERROR

    return response.json(), HTTPStatus.OK


@app.route('/result?task_id=<int:id_>', methods=["GET"])
def proxy_result(id_: int) -> Response:
    """
    Obtain and decrypt all results to belong to a certain task

    Parameters
    ----------
    id : int
        Task id from which the results need to be obtained

    Returns
    -------
    requests.Response
        Reponse from the vantage6 server
    """
    # We need the server io for the decryption of the results
    client = app.config.get("SERVER_IO")
    if not client:
        return jsonify({'msg': 'Proxy server not initialized properly'}),\
            HTTPStatus.INTERNAL_SERVER_ERROR

    # Forward the request
    try:
        response: Response = make_proxied_request(f"result?task_id={id_}")
    except Exception:
        log.exception(f'Error on "result?task_id={id_}"')
        return {'msg': 'Request failed, see node logs'},\
            HTTPStatus.INTERNAL_SERVER_ERROR

    # Attempt to decrypt the results. The enpoint should have returned
    # a list of results
    unencrypted = []
    runs = get_response_json_and_handle_exceptions(response)
    for run in runs:
        run = decrypt_result(run)
        unencrypted.append(run)

    return jsonify(unencrypted), HTTPStatus.OK


@app.route('/run/<int:id>', methods=["GET"])
def proxy_runs(id_: int) -> Response:
    """
    Obtain and decrypt the algorithm run from the vantage6 server to be used by
    an algorithm container.

    Parameters
    ----------
    id_ : int
        Id of the run to be obtained

    Returns
    -------
    requests.Response
        Response of the vantage6 server
    """
    # We need the server io for the decryption of the results
    client: NodeClient = app.config.get("SERVER_IO")
    if not client:
        return {'msg': 'Proxy server not initialized properly'},\
            HTTPStatus.INTERNAL_SERVER_ERROR

    # Make the proxied request
    try:
        response: Response = make_proxied_request(f"run/{id_}")
    except Exception:
        log.exception('Error on /run/<int:id>')
        return {'msg': 'Request failed, see node logs...'},\
            HTTPStatus.INTERNAL_SERVER_ERROR

    # Try to decrypt the results
    run = get_response_json_and_handle_exceptions(response)
    run = decrypt_result(run)

    return run, HTTPStatus.OK


@app.route('/<path:central_server_path>', methods=["GET", "POST", "PATCH",
                                                   "PUT", "DELETE"])
def proxy(central_server_path: str) -> Response:
    """
    Generalized http proxy request

    Parameters
    ----------
    central_server_path : str
        The endpoint on the server to be reached

    Returns
    -------
    requests.Response
        Contains the server response
    """
    try:
        response = make_proxied_request(central_server_path)
    except Exception:
        log.exception('Generic proxy endpoint')
        return {'msg': 'Request failed, see node logs'},\
            HTTPStatus.INTERNAL_SERVER_ERROR

    return response.content, response.status_code, response.headers.items()
