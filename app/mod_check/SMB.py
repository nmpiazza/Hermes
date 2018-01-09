from ..mod_check import app
from smb.SMBConnection import SMBConnection
from celery.utils.log import get_task_logger
from logging import DEBUG
from io import BytesIO
from os.path import dirname, basename

logger = get_task_logger(__name__)
logger.setLevel(DEBUG)

# scoring share name and check file name
scoring_share = 'scoring'
scoring_check_path = '/scoring.txt'


@app.task
def check(host, port, username, password, remote_name):
    result = None

    try:
        # create an SMBConnection object and connect to the server
        conn = SMBConnection(username=username, password=password, my_name='Hermes', remote_name=remote_name)
        conn.connect(host, port, timeout=5)

        # get a list of share names from the server and make sure the scoring share exists
        share_names = [share.name for share in conn.listShares(timeout=2)]
        if scoring_share in share_names:
            # get a list of files from the scoring share and make sure the check file exists
            share_files = [f.filename for f in conn.listPath(scoring_share, dirname(scoring_check_path), timeout=2)]
            if basename(scoring_check_path) in share_files:
                # create a BytesIO file object to write the file contents into
                file_obj = BytesIO()

                # read the scoring check file from the server and set it as the result
                conn.retrieveFile(scoring_share, scoring_check_path, file_obj, timeout=2)
                result = file_obj.getvalue().decode('utf8')

                # clean up
                file_obj.close()
            else:
                logger.error('Check file not found in share')
                result = False
        else:
            logger.error('No share named %s. Share names: %s', scoring_share, share_names)
            result = False
    except Exception as e:
        logger.exception(e)

    return result