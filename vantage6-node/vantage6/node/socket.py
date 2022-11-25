import logging
import datetime as dt

from socketio import ClientNamespace

from vantage6.common.task_status import TaskStatus, has_task_failed
from vantage6.node.util import logger_name


class NodeTaskNamespace(ClientNamespace):
    """Class that handles incoming websocket events."""

    # reference to the node objects, so a callback can edit the
    # node instance.
    node_worker_ref = None

    def __init__(self, *args, **kwargs):
        """ Handler for a websocket namespace.
        """
        super().__init__(*args, **kwargs)
        self.log = logging.getLogger(logger_name(__name__))

    def on_message(self, data):
        self.log.info(data)

    def on_connect(self):
        """On connect or reconnect"""
        self.log.info('(Re)Connected to the /tasks namespace')
        self.node_worker_ref.sync_task_queue_with_server()
        self.log.debug("Tasks synced again with the server...")

    def on_disconnect(self):
        """ Server disconnects event."""
        # self.node_worker_ref.socketIO.disconnect()
        self.log.info('Disconnected from the server')

    def on_new_task(self, task_id):
        """ New task event."""
        if self.node_worker_ref:
            self.node_worker_ref.get_task_and_add_to_queue(task_id)
            self.log.info(f'New task has been added task_id={task_id}')

        else:
            self.log.critical(
                'Task Master Node reference not set is socket namespace'
            )

    def on_algorithm_status_change(self, data):
        """
        An algorithm container in the collaboration has changed its status.

        Parameters
        ----------
        data: Dict
            Dictionary with relevant data to the status change. Should include:
            run_id: int
                run_id of the algorithm container that changed status
            status: str
                New status of the algorithm container
        """
        # TODO handle run sequence at this node. Maybe terminate all
        #     containers with the same run_id?
        status = data.get('status')
        run_id = data.get('run_id')
        if has_task_failed(status):
            self.log.critical(
                f"A container on a node within your collaboration part of "
                f"run_id={run_id} has exited with status {status}"
            )
        # else: no need to print to node logs that a task has started/
        # finished/... on another node

    def on_expired_token(self, msg):
        self.log.warning("Your token is no longer valid... reconnecting")
        self.node_worker_ref.socketIO.disconnect()
        self.log.debug("Old socket connection terminated")
        self.node_worker_ref.server_io.refresh_token()
        self.log.debug("Token refreshed")
        self.node_worker_ref.connect_to_socket()
        self.log.debug("Connected to socket")
        self.node_worker_ref.sync_task_queue_with_server()
        self.log.debug("Tasks synced again with the server...")

    def on_kill_containers(self, kill_info):
        self.log.info(f"Received instruction to kill task: {kill_info}")
        killed_ids = self.node_worker_ref.kill_containers(kill_info)
        for killed in killed_ids:
            self.log.debug(f"Set status of killed result {killed['result_id']}"
                           f" (task {killed['task_id']}).")
            self.node_worker_ref.server_io.patch_results(
                killed['result_id'], {
                    'status': TaskStatus.KILLED.value,
                    'finished_at': dt.datetime.now().isoformat()
                }
            )
            self.emit(
                "algorithm_status_change",
                {
                    'result_id': killed['result_id'],
                    'task_id': killed['task_id'],
                    'collaboration_id':
                        self.node_worker_ref.server_io.collaboration_id,
                    'node_id': self.node_worker_ref.server_io.whoami.id_,
                    'status': TaskStatus.KILLED.value,
                    'organization_id':
                        self.node_worker_ref.server_io.whoami.organization_id,
                    'is_subtask': killed['is_subtask'],
                },
                namespace='/tasks'
            )
