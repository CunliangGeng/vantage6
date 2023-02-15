.. _use-node:

Use
----

This section explains which commands are available to manage your node.

Quick start
^^^^^^^^^^^

To create a new node, run the command below. A menu will be started that
allows you to set up a node configuration file. For more details, check
out the :ref:`configure-node` section.

::

   vnode new

To run a node, execute the command below. The ``--attach`` flag will
cause log output to be printed to the console.

::

   vnode start --name <your_node> --attach

Finally, a node can be stopped again with:

::

   vnode stop --name <your_node>

Available commands
^^^^^^^^^^^^^^^^^^

Below is a list of all commands you can run for your node(s). To see all
available options per command use the ``--help`` flag,
i.e. ``vnode start --help`` .

+---------------------+------------------------------------------------+
| **Command**         | **Description**                                |
+=====================+================================================+
| ``vnode new``       | Create a new node configuration file           |
+---------------------+------------------------------------------------+
| ``vnode start``     | Start a node                                   |
+---------------------+------------------------------------------------+
| ``vnode stop``      | Stop one or all nodes                          |
+---------------------+------------------------------------------------+
| ``vnode files``     | List the files of a node                       |
+---------------------+------------------------------------------------+
| ``vnode attach``    | Print the node logs to the console             |
+---------------------+------------------------------------------------+
| ``vnode list``      | List all available nodes                       |
+---------------------+------------------------------------------------+
| ``vnode             | Create and upload a new public key for your    |
| create-private-key``| organization                                   |
+---------------------+------------------------------------------------+
