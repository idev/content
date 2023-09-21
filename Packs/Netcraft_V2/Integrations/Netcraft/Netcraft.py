import demistomock as demisto  # noqa: F401
from CommonServerPython import *  # noqa: F401
from collections.abc import Callable, Generator, Iterable
from math import ceil
import base64
import yaml


''' CONSTANTS '''

PARAMS: dict = demisto.params()
TAKEDOWN_API_LIMIT = 100_000
SUBMISSION_API_LIMIT = 1000
MAX_FETCH_DEFAULT = 10
TAKEDOWN_OK_CODE = 'TD_OK'
AUTH_HEADERS = {
    'Authorization': f'Bearer {PARAMS["credentials"]["password"]}'
}
SERVICE_TO_URL_MAP = {
    'takedown': PARAMS['takedown_url'],
    'submission': PARAMS['submission_url'],
}
RES_CODE_TO_MESSAGE = {
    TAKEDOWN_OK_CODE: 'The attack was submitted to Netcraft successfully.',
    'TD_EXISTS': 'The attack was not submitted to Netcraft because it already exists in the system.',
    'TD_WILDCARD': 'The attack was not submitted because it is a wildcard sub-domain variation of an existing takedown.',
    'TD_VERIFY':
        'The submitted content is undergoing additional verification to ensure that it is a valid takedown target.'
        ' If verification is successful, a new takedown will be submitted. If not, no takedown will be created.\n'
        'To get a list of all takedowns, run the command: "netcraft-takedown-list"',
}

''' CLIENT CLASS '''


class Client(BaseClient):

    def takedown_http_request(self, method: str, url_suffix: str,
                              params: dict = None, data: dict = None,
                              files: dict = None, resp_type: str = 'json',
                              ok_codes: Any = None, **kwargs) -> Any:
        '''
        A wrapper for BaseClient._http_request that interacts with the Netcraft takedown service.
        Args:
            method (str):
                The HTTP method, for example: GET, POST, and so on.
            url_suffix (str):
                The API endpoint.
            params (dict):
                URL parameters to specify the query.
            json_data (dict):
                The dictionary to send in a 'POST' request.
            files (dict):
                The file data to send in a 'POST' request.
            resp_type (str):
                Determines which data format to return from the HTTP request. The default
                is 'json'. Other options are 'text', 'content', 'xml' or 'response'. Use 'response'
                    to return the full response object.
            ok_codes (tuple[int]):
                The request codes to accept as OK, for example: (200, 201, 204). If you specify "None", will use self._ok_codes.
        Returns:
            dict | str | bytes | xml.etree.ElementTree.Element | requests.Response: Depends on the resp_type parameter
        '''
        remove_nulls_from_dictionary(params or {})
        remove_nulls_from_dictionary(data or {})
        return self._http_request(
            method, full_url=urljoin(self._base_url['takedown'], url_suffix),
            params=params, data=data, files=files, resp_type=resp_type,
            ok_codes=ok_codes, **kwargs)

    def submission_http_request(self, method: str, url_suffix: str,
                                params: dict = None, json_data: dict = None,
                                files: dict = None, resp_type: str = 'json',
                                ok_codes: Any = None, **kwargs) -> Any:
        '''
        A wrapper for BaseClient._http_request that interacts with the Netcraft submission service.
        Args:
            method (str):
                The HTTP method, for example: GET, POST, and so on.
            url_suffix (str):
                The API endpoint.
            params (dict):
                URL parameters to specify the query.
            json_data (dict):
                The dictionary to send in a 'POST' request.
            files (dict):
                The file data to send in a 'POST' request.
            resp_type (str):
                Determines which data format to return from the HTTP request. The default
                is 'json'. Other options are 'text', 'content', 'xml' or 'response'. Use 'response'
                    to return the full response object.
            ok_codes (tuple[int]):
                The request codes to accept as OK, for example: (200, 201, 204). If you specify "None", will use self._ok_codes.
        Returns:
            dict | str | bytes | xml.etree.ElementTree.Element | requests.Response: Depends on the resp_type parameter
        '''
        remove_nulls_from_dictionary(params or {})
        remove_nulls_from_dictionary(json_data or {})
        return self._http_request(
            method, full_url=urljoin(self._base_url['submission'], url_suffix),
            params=params, json_data=json_data, files=files, resp_type=resp_type,
            ok_codes=ok_codes, **kwargs)

    def client_error_handler(self, res: requests.Response):
        '''Error handler for Netcraft API call error'''
        err_msg = f'Error in Netcraft API call [{res.status_code}] - {res.reason}\n'
        try:
            # return a more readable error
            err_msg += yaml.safe_dump(res.json())
        except ValueError:
            err_msg += res.text
        raise DemistoException(err_msg, res=res)

    def get_takedowns(self, params: dict) -> list[dict]:
        '''Used by fetch-incidents and netcraft-takedown-list'''
        return self.takedown_http_request(
            'GET', 'attacks/', params=params,
        )

    def attack_report(self, body: dict, file: dict | None) -> str:
        return self.takedown_http_request(
            'POST', 'report/',
            data=body, resp_type='text', files=file,
        )

    def takedown_update(self, body: dict) -> dict:
        return self.takedown_http_request(
            'POST', 'update-attack/', data=body,
        )

    def takedown_escalate(self, body: dict) -> dict:
        return self.takedown_http_request(
            'POST', 'escalate/', data=body,
        )

    def takedown_note_create(self, body: dict) -> dict:
        return self.takedown_http_request(
            'POST', 'notes/', data=body,
        )

    def takedown_note_list(self, params: dict) -> list[dict]:
        return self.takedown_http_request(
            'GET', 'notes/', params=params,
        )

    def attack_type_list(self, params: dict) -> list[dict]:
        return self.takedown_http_request(
            'GET', 'attack-types/', params=params,
        )

    def submission_list(self, params: dict) -> dict:
        return self.submission_http_request(
            'GET', 'submissions/', params=params,
        )

    def get_submission(self, uuid: str, ignore_404: bool) -> dict:
        return self.submission_http_request(
            'GET', f'submission/{uuid}', ok_codes=(200, 404 * ignore_404)
        )

    def file_report_submit(self, body: dict) -> dict:
        return self.submission_http_request(
            'POST', 'report/files', json_data=body,
        )

    def submission_file_list(self, submission_uuid, params: dict) -> dict:
        return self.submission_http_request(
            'GET', f'submission/{submission_uuid}/files', params=params,
        )

    def file_screenshot_get(self, submission_uuid: str, file_hash: str) -> requests.Response:
        return self.submission_http_request(
            'GET', f'submission/{submission_uuid}/files/{file_hash}/screenshot',
            resp_type='response', ok_codes=(200, 404)
        )

    def url_report_submit(self, body: dict) -> dict:
        return self.submission_http_request(
            'POST', 'report/urls', json_data=body,
        )

    def submission_mail_get(self, submission_uuid: str) -> dict:
        return self.submission_http_request(
            'GET', f'submission/{submission_uuid}/mail',
        )

    def mail_screenshot_get(self, submission_uuid: str) -> requests.Response:
        return self.submission_http_request(
            'GET', f'submission/{submission_uuid}/mail/screenshot',
            resp_type='response', ok_codes=(200, 404)
        )

    def email_report_submit(self, body: dict) -> dict:
        return self.submission_http_request(
            'POST', 'report/mail', json_data=body,
        )

    def submission_url_list(self, submission_uuid, params: dict) -> dict:
        return self.submission_http_request(
            'GET', f'submission/{submission_uuid}/urls', params=params,
        )

    def url_screenshot_get(self, submission_uuid: str, url_uuid: str, screenshot_hash: str) -> requests.Response:
        return self.submission_http_request(
            'GET', f'submission/{submission_uuid}/urls/{url_uuid}/screenshots/{screenshot_hash}',
            resp_type='response',
        )


''' HELPER FUNCTIONS '''


def sub_dict(d: dict, *keys) -> dict:
    '''Returns a sub dict of d with the given keys'''
    return {k: d.get(k) for k in keys}


def pop_keys(d: dict, *keys) -> dict:
    '''Removes the given keys of d and returns them as their own dict'''
    return {k: d.pop(k, None) for k in keys}


def int_to_readable_bool(val: str | int | None) -> str | None:
    '''
    Converts the 1 or 0 values returned by netcraft to a human readable string.
    The val provided can be an int, str or None (in which case None should be returned).
    '''
    return {'0': 'No', '1': 'Yes'}.get(str(val))


def int_to_bool(val: str | int | None) -> bool | None:
    '''
    Converts the 1 or 0 values returned by netcraft to a boolean for the context, if possible.
    The val provided can be an int, str or None (in which case None should be returned).
    '''
    return {'0': False, '1': True}.get(str(val))


def convert_binary_keys_to_bool(d: dict, *keys):
    '''Converts values of specified keys in a dictionary to booleans.

    This takes a dictionary and list of keys, and converts the values of those keys
    in the dictionary to True/False based on their string or int values of "0", "1", 0 or 1.

    Args:
        d (dict): The dictionary to modify in-place.
        *keys: The list of keys in the dictionary to convert.

    Returns:
        None

    Examples:
        >>> d = {'a': '1', 'b': '0'}
        >>> convert_binary_keys_to_bool(d, 'a', 'b')
        >>> print(d)
        {'a': True, 'b': False}
    '''
    d |= {
        key: int_to_bool(d.get(key))
        for key in keys
    }


def read_base64encoded_file(filepath: str) -> str:
    '''Returns a base64 encoded string of the file'''
    with open(filepath, 'rb') as f:
        return base64.b64encode(f.read()).decode()


def paginate_with_token(
    client_func: Callable[[dict], dict],
    api_params: dict[str, Any],
    limit: str | int | None,
    page_size: str | int | None,
    next_token: str | None,
    pages_key_path: Iterable | None = (),
    api_limit: int = 1000,
    api_token_key: str = 'marker',
    api_page_size_key: str = 'page_size',
    stop_on_token: Any = None,
) -> tuple[list, Any]:
    '''
    Paginates an API endpoint that accepts "page token" and "page size" parameters
    using the "limit", "next_token" and "page_size" args provided by demisto.args() as per the XSOAR pagination protocol.

    Args:
        client_func (Callable[[dict], dict]): The client function that calls the API endpoint.
        api_params (dict[str, Any]): The parameters to call the endpoint with. The pagination args will be added to this arg.
        limit (str | int | None): The demisto.args() limit.
        page (str | None): The demisto.args() page.
        page_size (str | int | None): The demisto.args() page_size.
        pages_key_path (Iterable | None): The keys used to extract the "pages" returned by the API.
                                          i.e. If the API returns a JSON in the format: {'data': {'pages': [1,2,3,4,5]}},
                                          then pages_key_path=('data', 'pages'). The key path MUST point to a list.
        api_limit (int, optional): The maximum amount of data returned by the API on a single call. Defaults to 1000.
        api_token_key (str, optional): The key used by the API as a page token.
                                       This will be used both for the API call and response. Defaults to 'marker'.
        api_page_size_key (str, optional): The key used by the API as a page size. Defaults to 'page_size'.
        stop_on_token (Any): The token returned by the API that indicates the end of the existing data. Defaults to = None

    Returns:
        tuple[list, Any]: The combined pages and the next page token.
    '''

    def page_sizes(limit: int, api_limit: int) -> Generator[int, None, None]:
        '''Generates page sizes for pagination based on the api_limit.
    
        This generates page sizes to use for pagination with
        where all but the last are the API limit and the last is the remainder.
        It yields page sizes until the total limit is reached.

        Args:
            limit: The total number of results to fetch.
            api_limit: The limit the API has per page/request.

        Yields: 
            int: The next page size to use, not exceeding the API limit.
        '''
        while limit > api_limit:
            yield api_limit
            limit -= api_limit
        yield limit

    def get_page(pagination_args: dict) -> tuple[list, Any]:
        response = client_func(api_params | pagination_args)
        return (
            dict_safe_get(response, keys=pages_key_path, return_type=list),
            response.get(api_token_key)
        )

    page_size = min(api_limit, arg_to_number(page_size) or api_limit)

    if next_token:
        pagination_args = {api_token_key: next_token, api_page_size_key: page_size}
        return get_page(pagination_args)
    else:
        pages = []
        for page_size in page_sizes(arg_to_number(limit) or 50, api_limit):
            pagination_args = {api_token_key: next_token, api_page_size_key: page_size}
            new_page, next_token = get_page(pagination_args)
            pages += new_page
            if next_token == stop_on_token:
                break
        return pages, next_token


def paginate_with_page_num_and_size(
    client_func: Callable,
    *func_args,
    limit: str | int | None = 50,
    page: str | int | None = None,
    page_size: str | int | None = None,
    pages_key_path: Iterable | None = (),
    api_limit: int = 1000,
    api_page_num_key: str = 'page',
    api_page_size_key: str = 'count',
) -> list:
    '''
    Paginates an API endpoint that accepts "page number" and "page size" parameters
    using the "limit", "page" and "page_size" args provided by demisto.args() as per the XSOAR pagination protocol.

    Args:
        client_func (Callable[[...], dict]): The client function that calls the API endpoint.
        api_params (dict[str, Any]): The parameters to call the endpoint with. The pagination args will be added to this arg.
        limit (str | int | None): The demisto.args() limit.
        page (str | None): The demisto.args() page.
        page_size (str | int | None): The demisto.args() page_size.
        pages_key_path (Iterable | None): The keys used to extract the "pages" returned by the API.
                                          i.e. If the API returns a JSON in the format: {'data': {'pages': [1,2,3,4,5]}},
                                          then pages_key_path=('data', 'pages'). The key path MUST point to a list.
        api_limit (int, optional): The maximum amount of data returned by the API on a sngle call. Defaults to 1000.
        api_page_num_key (str, optional): The key used by the API as a page number/index. Defaults to 'page'.
        api_page_size_key (str, optional): The key used by the API as a page size. Defaults to 'count'.

    Returns:
        list: The combined pages.
    '''
    def get_page(pagination_args: dict) -> list[dict]:
        response = client_func(*func_args, pagination_args)
        return dict_safe_get(response, keys=pages_key_path, return_type=list)

    page = arg_to_number(page)
    page_size = arg_to_number(page_size)

    if page and page_size:
        pagination_args = {api_page_num_key: page, api_page_size_key: min(api_limit, page_size)}
        return get_page(pagination_args)
    else:
        limit = arg_to_number(limit) or 50
        pages = []
        for page in range(1, ceil(limit / api_limit) + 1):
            pagination_args = {api_page_num_key: page, api_page_size_key: api_limit}
            new_page = get_page(pagination_args)
            pages += new_page
            if len(new_page) < api_limit:  # end of the data has been reached
                break
        del pages[limit:]  # remove the surplus
        return pages


''' COMMAND FUNCTIONS '''


def test_module(client: Client) -> str:
    if PARAMS.get('isFetch') and not arg_to_datetime(PARAMS['first_fetch']):
        raise ValueError(f'{PARAMS["first_fetch"]!r} is not a valid time.')
    client.get_takedowns({'page_size': 1})  # test takedown service
    client.submission_list({'max_results': 1})  # test submission service
    return 'ok'


def fetch_incidents(client: Client) -> list[dict[str, str]]:
    # demisto.getLastRun and demisto.setLastRun hold takedown IDs
    def to_xsoar_incident(incident: dict) -> dict:

        demisto.debug(incident_id := incident['id'])
        return {
            'name': f'Takedown-{incident_id}',
            'occurred': arg_to_datetime(  # type: ignore[union-attr]
                incident['date_submitted'],
                required=True
            ).isoformat(),
            'rawJSON': json.dumps(incident),
        }

    params = {
        'max_results': min(
            arg_to_number(PARAMS['max_fetch']) or MAX_FETCH_DEFAULT,
            TAKEDOWN_API_LIMIT
        ),
        'sort': 'id',
        'region': PARAMS['region']
    }

    if last_run := demisto.getLastRun():
        last_id = last_run['id']
        params['id_after'] = last_id
        demisto.debug(f'Fetching IDs from: {last_id}')
    else:
        last_id = None
        params['date_from'] = str(
            arg_to_datetime(
                PARAMS['first_fetch'],
                required=True
            ))
        demisto.debug(f'First fetch date: {params["date_from"]}')

    incidents = client.get_takedowns(params) or []
    if incidents:
        demisto.setLastRun({'id': incidents[-1]['id']})
        # the first incident from the API call should be a duplicate of last_id
        if incidents[0]['id'] == last_id:
            del incidents[0]

    return list(map(to_xsoar_incident, incidents))


def attack_report_command(args: dict, client: Client) -> CommandResults:

    def args_to_api_body_and_file(args: dict) -> tuple[dict, dict | None]:
        if entry_id := args.get('entry_id'):
            file_contents = demisto.getFilePath(entry_id)
            file = {'evidence': open(file_contents['path'], 'rb')}
        else:
            file = None

        return args | {
            'type': args.pop('attack_type'),
            'suspected_fraudulent_domain': argToBoolean(args.pop('suspected_fraud_domain')),
            'region': args.get('region') or PARAMS['region'],
            'malware': json.loads(args.get('malware', 'null')),
            'force_auth': json.loads(args.get('force_auth', 'null')),
            'inactive': json.loads(args.get('inactive', 'null')),
            'tags': ','.join(argToList(args.get('tags'))),
        }, file

    def response_to_outputs(response: str) -> dict[str, Any]:
        '''Returns the commands context and readable outputs'''
        # the response contains one or two lines inf the form "<code>\n<id (if it exists)>"
        code, takedown_id, *rest = response.splitlines() + ['']
        table = {
            'Report status': RES_CODE_TO_MESSAGE.get(code, ' '.join(rest)),
            'Takedown ID': takedown_id,
            'Response code': code,
        }
        return {
            'outputs': {'id': takedown_id} if code == TAKEDOWN_OK_CODE else None,
            'readable_output': tableToMarkdown(
                'Netcraft Takedown',
                table, list(table),
                removeNull=True
            )
        }

    response = client.attack_report(
        *args_to_api_body_and_file(args)
    )
    return CommandResults(
        outputs_prefix='Netcraft.Takedown',
        outputs_key_field='id',
        raw_response=response,
        **response_to_outputs(response)
    )


def takedown_list_command(args: dict, client: Client) -> CommandResults:

    def args_to_params(args: dict) -> dict:
        return args | {
            'authgiven': args.pop('auth_given', '').lower().replace(' ', ':'),
            'escalated': args.pop('escalated', '').lower().replace(' ', ':'),
            'report_source': {
                'Phishing Feed': 'phish_feed',
                'Interface': 'interface',
                'Referer': 'referer',
                'Forensic': 'forensic',
                'Api': 'api',
                'Email Feed': 'email_feed',
                'Fraud Detection': 'fraud_detection'
            }.get(args.get('report_source', '')),
            'sort': {
                'Auth Given': 'authgiven',
                'Customer Label': 'customer_label',
                'Date Submitted': 'date_submitted',
                'Hoster': 'hoster',
                'Id': 'id',
                'Ip': 'ip',
                'Language': 'language',
                'Last Updated': 'last_updated',
                'Registrar': 'registrar',
                'Status': 'status'
            }.get(args.get('sort', '')),
            'statuses': ','.join(argToList(args.get('statuses'))),
            'dir': args.pop('sort_direction'),
            'max_results':
                arg_to_number(args.pop('limit'))
                if not argToBoolean(args.pop('all_results'))
                else TAKEDOWN_API_LIMIT,
            'region': args.get('region') or PARAMS['region']
        }

    def response_to_readable(response: list[dict]) -> str:
        return tableToMarkdown(
            'Netcraft Takedowns',
            [
                {
                    'ID': d.get('id'),
                    'Auth': int_to_readable_bool(d.get('authgiven')),
                    'Brand': d.get('target_brand'),
                    'Attack Type': d.get('attack_type'),
                    'Status': d.get('status'),
                    'Attack URL': d.get('attack_url'),
                    'Date Reported': d.get('date_submitted'),
                    'Last Updated': d.get('last_updated'),
                    'Date Authorised': d.get('date_authed') or 'N/A',
                    'Date Escalated': d.get('date_escalated') or 'N/A',
                    'First Contact': d.get('first_contact'),
                    'First Inactive (Monitoring)': d.get('first_inactive') or 'N/A',
                    'First Resolved': d.get('first_resolved') or 'N/A',
                }
                for d in response
            ],
            [
                'ID', 'Auth', 'Brand', 'Attack Type', 'Status', 'Attack URL',
                'Date Reported', 'Last Updated', 'Date Authorised', 'Date Escalated',
                'First Contact', 'First Inactive (Monitoring)', 'First Resolved'
            ],
            removeNull=True
        )

    response = client.get_takedowns(
        args_to_params(args)
    )
    return CommandResults(
        readable_output=response_to_readable(response),
        outputs_prefix='Netcraft.Takedown',
        outputs_key_field='id',
        outputs=response,
    )


def takedown_update_command(args: dict, client: Client) -> CommandResults:

    def args_to_params(args: dict) -> dict:
        return {
            key: args.get(value)
            for key, value in
            (
                ('set_customer_label', 'customer_label'),
                ('set_description', 'description'),
                ('set_region', 'region'),
                ('set_brand', 'brand'),
                ('set_suspected_fraudulent_domain', 'suspected_fraud_domain'),
                ('set_suspected_fraudulent_hostname', 'suspected_fraud_hostname'),
            )
        } | {
            'add_tags': ','.join(argToList(args.get('add_tags'))),
            'remove_tags': ','.join(argToList(args.get('remove_tags'))),
            'takedown_id': args.get('takedown_id')
        }

    response = client.takedown_update(
        args_to_params(args)
    )
    if not response.get('takedown_id'):
        raise DemistoException(
            f'Error in Netcraft API call:\n{yaml.dump(response)}'
        )
    return CommandResults(
        readable_output=tableToMarkdown(
            'Takedown successfully updated.',
            {'Takedown ID': response['takedown_id']},
            ['Takedown ID']
        ),
        raw_response=response
    )


def takedown_escalate_command(args: dict, client: Client) -> CommandResults:
    response = client.takedown_escalate(args)
    if response.get('status') != TAKEDOWN_OK_CODE:
        raise DemistoException(
            f'Error in Netcraft API call:\n{yaml.dump(response)}'
        )
    return CommandResults(
        raw_response=response,
        readable_output=tableToMarkdown(
            'Takedown successfully escalated.',
            {'Takedown ID': args['takedown_id']},
            ['Takedown ID']
        )
    )


def takedown_note_create_command(args: dict, client: Client) -> CommandResults:
    response = client.takedown_note_create(
        args | {'text': args.pop('note_text')}
    )
    if not response.get('note_id'):
        raise DemistoException(
            f'Error in Netcraft API call:\n{yaml.dump(response)}'
        )
    return CommandResults(
        outputs_prefix='Netcraft.TakedownNote',
        outputs=response,
        outputs_key_field='note_id',
        readable_output=tableToMarkdown(
            'Note successfully added to takedown.',
            {'Note ID': response['note_id'],
             'Takedown ID': args['takedown_id']},
            ['Note ID', 'Takedown ID']
        )
    )


def takedown_note_list_command(args: dict, client: Client) -> CommandResults:

    def response_to_readable(response: list[dict]) -> str:
        header_map = {
            'note_id': 'Note ID',
            'takedown_id': 'Takedown ID',
            'group_id': 'Group ID',
            'time': 'Time',
            'author': 'Author',
            'note': 'Note'
        }
        return tableToMarkdown(
            'Takedown Notes', response, list(header_map),
            headerTransform=header_map.get,
            removeNull=True
        )

    response = client.takedown_note_list({
        'takedown_id': args.get('takedown_id'),
        'author': args.get('author_mail')
    })
    response = response if argToBoolean(args['all_results']) else response[:50]
    return CommandResults(
        outputs_prefix='Netcraft.TakedownNote',
        outputs=response,
        outputs_key_field='note_id',
        readable_output=response_to_readable(response)
    )


def attack_type_list_command(args: dict, client: Client) -> CommandResults:

    def response_to_readable(response: list[dict]) -> str:
        return tableToMarkdown(
            'Takedown Notes', response,
            [
                'name', 'display_name', 'base_type', 'description',
                'automated', 'auto_escalation', 'auto_authorise',
            ],
            headerTransform=string_to_table_header,
            removeNull=True
        )

    response = client.attack_type_list(
        sub_dict(args, 'auto_escalation', 'auto_authorise', 'automated')
        | {'region': args.get('region') or PARAMS['region']}
    )
    response = response if argToBoolean(args['all_results']) else response[:50]
    return CommandResults(
        outputs_prefix='Netcraft.AttackType',
        outputs=response,
        readable_output=response_to_readable(response)
    )


@polling_function(
    name='netcraft-submission-list',
    interval=arg_to_number(demisto.getArg('interval_in_seconds')),
    timeout=arg_to_number(demisto.getArg('timeout')),
    poll_message='Submission pending:'
)
def get_submission(args: dict, submission_uuid: str, client: Client) -> PollResult:

    def response_to_context(response: dict, uuid: str) -> dict:
        '''
        Does the following:
        1. adds the uuid the output so that there is a uuid for every submission under 'Netcraft.Submission'
            as is the the case with submission_list().
        2. keeps the context output somewhat similar to the output of the non uuid command call (submission_list) by aligning keys
            that differ in name only.
        3. converts 1 or 0 values into their corresponding boolean values.
        '''
        response |= {
            'uuid': uuid,
            'source_name': response.get('source', {}).pop('name', None),
            'submitter_email': response.pop('submitter', {}).get('email'),
        }
        convert_binary_keys_to_bool(
            response,
            'has_cryptocurrency_addresses', 'has_files', 'has_issues', 'has_mail',
            'has_phone_numbers', 'has_urls', 'is_archived', 'pending'
        )
        return response

    def response_to_readable(submission: dict) -> str:
        return tableToMarkdown(
            'Netcraft Submissions',
            {
                'Submission UUID': submission.get('uuid'),
                'Submission Date': str(arg_to_datetime(submission.get('date'))),
                'Submitter Email': submission.get('submitter_email'),
                'State': submission.get('state'),
                'Source': submission.get('source_name')
            },
            ['Submission UUID', 'Submission Date', 'Submitter Email', 'State', 'Source'],
            removeNull=True,
        )

    response = client.get_submission(submission_uuid, args['ignore_404'])
    return PollResult(
        CommandResults(
            outputs_prefix='Netcraft.Submission',
            outputs_key_field='uuid',
            outputs=response_to_context(response, submission_uuid),
            readable_output=response_to_readable(response),
        ),
        # the submission may not be registered yet, hence the "None" option.
        continue_to_poll=(response.get('state') in ('processing', None)),
        args_for_next_run=(args | {'submission_uuid': submission_uuid})
    )


def submission_list(args: dict, client: Client) -> CommandResults:

    def args_to_params(args: dict) -> dict:
        return sub_dict(
            args,
            'source_name', 'state', 'submission_reason', 'submitter_email'
        ) | {
            'date_start':
                str(date.date())
                if (date := arg_to_datetime(args.get('date_start')))
                else None,
            'date_end':
                str(date.date())
                if (date := arg_to_datetime(args.get('date_end')))
                else None,
        }

    def response_to_readable(submissions: list[dict]) -> str:
        return tableToMarkdown(
            'Netcraft Submissions',
            [
                {
                    'Submission UUID': sub.get('uuid'),
                    'Submission Date': str(arg_to_datetime(sub.get('date'))),
                    'Submitter Email': sub.get('submitter_email'),
                    'State': sub.get('state'),
                    'Source': sub.get('source_name')
                }
                for sub in submissions
            ],
            ['Submission UUID', 'Submission Date', 'Submitter Email', 'State', 'Source'],
            removeNull=True,
        )

    submissions, next_token = paginate_with_token(
        client.submission_list,
        api_params=args_to_params(args),
        **sub_dict(args, 'limit', 'page_size', 'next_token'),
        pages_key_path=['submissions']
    )
    return CommandResults(
        # this method is used so that the key Netcraft.SubmissionNextToken is overridden on each run
        outputs={
            'Netcraft.Submission(val.uuid && val.uuid == obj.uuid)': submissions,
            'Netcraft(val.SubmissionNextToken || true)': {'SubmissionNextToken': next_token}
        },
        readable_output=response_to_readable(submissions),
    )


def submission_list_command(args: dict, client: Client) -> CommandResults:
    if uuid := args.pop('submission_uuid', None):
        return get_submission(args, uuid, client)
    else:
        return submission_list(args, client)


def file_report_submit_command(args: dict, client: Client) -> CommandResults:

    def validate_args(args: dict):  # TODO add tests
        if not (
            (
                args.get('file_content')
                and args.get('file_name')
            )
            or args.get('entry_id')
        ):
            raise DemistoException('A file must be provided. Use file_content and file_name OR entry_id')

    def args_to_body(args: dict) -> dict:
        content = args.pop('file_content', None)
        name = args.pop('file_name', None)
        entry_ids = argToList(args.pop('entry_id', None))
        files = [
            {
                'content': content,
                'filename': name,
            }
        ] if content and name else [
            {
                'content': read_base64encoded_file(file['path']),
                'filename': file['name'],
            }
            for file in map(demisto.getFilePath, entry_ids)
        ]
        return {
            'email': args.pop('reporter_email'),
            'reason': args.pop('reason', None),
            'files': files,
        }

    response = client.file_report_submit(
        args_to_body(args)
    )
    return get_submission(args | {'ignore_404': True}, response['uuid'], client)


def submission_file_list_command(args: dict, client: Client) -> CommandResults:

    def response_to_readable(files: list[dict]) -> str:
        return tableToMarkdown(
            'Submission Files',
            files,
            ['filename', 'hash', 'file_state'],
            headerTransform={
                'filename': 'Filename',
                'hash': 'Hash',
                'file_state': 'Classification',
            }.get,
            removeNull=True,
        )

    def response_to_context(files: list[dict]) -> list[dict]:
        for file in files:
            convert_binary_keys_to_bool(file, 'has_screenshot')
        return files

    files = paginate_with_page_num_and_size(
        client.submission_file_list,
        args['submission_uuid'],
        **sub_dict(args, 'limit', 'page_size', 'page'),
        pages_key_path=('files',)
    )
    return CommandResults(
        readable_output=response_to_readable(files),
        outputs=response_to_context(files),
        outputs_prefix='Netcraft.SubmissionFile',
        outputs_key_field='hash',
    )


def file_screenshot_get_command(args: dict, client: Client) -> dict | CommandResults:
    response = client.file_screenshot_get(**args)
    if response.status_code == 404:
        return CommandResults(
            readable_output='No screenshot for file.'
        )
    return fileResult(
        f'file_screenshot_{args["file_hash"]}.png',
        response.content,
        EntryType.ENTRY_INFO_FILE,
    )


def email_report_submit_command(args: dict, client: Client) -> CommandResults:

    response = client.email_report_submit(
        {'email': args.pop('reporter_email')} | pop_keys(args, 'message', 'password')
    )
    return get_submission(args | {'ignore_404': True}, response['uuid'], client)


def submission_mail_get_command(args: dict, client: Client) -> CommandResults:

    def response_to_readable(mail: dict) -> str:
        return tableToMarkdown(
            'Submission Mails',
            mail,
            ['subject', 'from', 'to', 'state'],
            headerTransform={
                'subject': 'Subject',
                'from': 'From',
                'to': 'To',
                'state': 'Classification',
            }.get,
            removeNull=True,
        )

    response = client.submission_mail_get(**args)
    return CommandResults(
        outputs=response,
        outputs_prefix='Netcraft.SubmissionMail',
        outputs_key_field='hash',
        readable_output=response_to_readable(response),
    )


def mail_screenshot_get_command(args: dict, client: Client) -> dict | CommandResults:
    response = client.mail_screenshot_get(**args)
    if response.status_code == 404:
        return CommandResults(
            readable_output='No screenshot for mail.'
        )
    return fileResult(
        f'mail_screenshot_{args["submission_uuid"]}.png',
        response.content,
        EntryType.ENTRY_INFO_FILE,
    )


def url_report_submit_command(args: dict, client: Client) -> CommandResults:

    response = client.url_report_submit({
        'email': args.pop('reporter_email'),
        'reason': args.pop('reason', None),
        'urls': [
            {'url': url} for url in argToList(args.pop('urls'))
        ]
    })
    return get_submission(args | {'ignore_404': True}, response['uuid'], client)


def submission_url_list_command(args: dict, client: Client) -> CommandResults:

    def response_to_readable(urls: list[dict]) -> str:
        return tableToMarkdown(
            'Submission URLs',
            [
                {
                    'URL': url.get('url'),
                    'Hostname': url.get('hostname'),
                    'Classification': url.get('url_state'),
                    'URL Classification Log': yaml.safe_dump(url.get('classification_log')),
                    'Screenshots': yaml.safe_dump(url.get('screenshots')),
                    'UUID': url.get('uuid')
                }
                for url in urls
            ],
            ['URL', 'Hostname', 'Classification', 'URL Classification Log', 'Screenshots', 'UUID'],
            removeNull=True,
        )

    urls = paginate_with_page_num_and_size(
        client.submission_url_list,
        args['submission_uuid'],
        **sub_dict(args, 'limit', 'page_size', 'page'),
        pages_key_path=('urls',)
    )
    return CommandResults(
        outputs=urls,
        outputs_key_field='uuid',
        outputs_prefix='Netcraft.SubmissionURL',
        readable_output=response_to_readable(urls)
    )


def url_screenshot_get_command(args: dict, client: Client) -> dict:
    response = client.url_screenshot_get(**args)
    # type of screenshot can be gif or png, the Content-Type key returns: "image/{file_type}"
    file_type = response.headers.get('Content-Type', '').partition('/')[2]
    return fileResult(
        f'url_screenshot_{args["screenshot_hash"]}.{file_type}',
        response.content,
        EntryType.ENTRY_INFO_FILE
    )


''' MAIN FUNCTION '''


def main() -> None:

    args = demisto.args()
    command = demisto.command()

    client = Client(
        base_url=SERVICE_TO_URL_MAP,
        verify=(not PARAMS['insecure']),
        proxy=PARAMS['proxy'],
        ok_codes=(200,),
        headers=AUTH_HEADERS,
    )

    demisto.debug(f'Command being called is {command}')
    try:
        match command:
            case 'test-module':
                return_results(test_module(client))
            case 'fetch-incidents':
                demisto.incidents(fetch_incidents(client))
            case 'netcraft-attack-report':
                return_results(attack_report_command(args, client))
            case 'netcraft-takedown-list':
                return_results(takedown_list_command(args, client))
            case 'netcraft-takedown-update':
                return_results(takedown_update_command(args, client))
            case 'netcraft-takedown-escalate':
                return_results(takedown_escalate_command(args, client))
            case 'netcraft-takedown-note-create':
                return_results(takedown_note_create_command(args, client))
            case 'netcraft-takedown-note-list':
                return_results(takedown_note_list_command(args, client))
            case 'netcraft-attack-type-list':
                return_results(attack_type_list_command(args, client))
            case 'netcraft-submission-list':
                return_results(submission_list_command(args, client))
            case 'netcraft-submission-file-list':
                return_results(submission_file_list_command(args, client))
            case 'netcraft-file-screenshot-get':
                return_results(file_screenshot_get_command(args, client))
            case 'netcraft-submission-mail-get':
                return_results(submission_mail_get_command(args, client))
            case 'netcraft-mail-screenshot-get':
                return_results(mail_screenshot_get_command(args, client))
            case 'netcraft-submission-url-list':
                return_results(submission_url_list_command(args, client))
            case 'netcraft-url-screenshot-get':
                return_results(url_screenshot_get_command(args, client))
            case 'netcraft-file-report-submit':
                return_results(file_report_submit_command(args, client))
            case 'netcraft-url-report-submit':
                return_results(url_report_submit_command(args, client))
            case 'netcraft-email-report-submit':
                return_results(email_report_submit_command(args, client))
            case _:
                raise NotImplementedError(f'{command!r} is not a Netcraft command.')

    except Exception as e:
        return_error(f'Failed to execute {command!r}.\nError: {e.__class__.__name__}\nCause: {e}')


''' ENTRY POINT '''

if __name__ in ('__main__', '__builtin__', 'builtins'):
    main()
