Visualise and manage progress and log information from large computations. The goal is to reduce the need for feedback on the command line and enable specialised applications for visualising notifications from software. Using Odin would give advanced reporting capabilities using very simple means in an application, leaving the developer to focus on the computational aspects rather than reporting details.
The Odin system must be light weight; the overhead should not be significantly worse than for writing updates to the terminal or a log file.

Use cases

- Progress bars
- Warnings and error messages

Goals

It should be super easy to extend a software to report progress. Perhaps like this in Python:
```
from odin import reporter
r = reporter.progressbar('A label here')
for i in range(100):
    do_whatever(i)
    r.report(i)
```
Not much more code than when using the logging framework in Python.
It should be possible to report from more than one programming language. Python and C++ are natural first candidates.
It should not matter whether a monitor is available to receive reports — the code should just work anyways. One could consider to have a backup solution to write to stderr or call some other user-defined function (say, logging.info() in Python) if the monitor (or ~/.odin) is not present. 
The over-arching goal: I want to reduce the amount of redundant progress output in the world.

Design ideas

I think there are two setups.
1. You monitor progress with access to the same file system as the computations. In that case, the computing processes write to a port, say ~/.odin, on which a monitor software visualizes the progress.
2. You monitor progress on a completely different computer from the computations and they cannot share file system. In this case one has to start a process (daemon?) on the computing system that listens on ~/.odin and forwards messages to the monitoring process on some other computer. I do not know how this is best implemented.
Any info sent over a network should (?) use UDP since we do not want messages to stack up. 
I would like to be able to update a progressbar, notify the monitor that a jobs is finished (but it should not be mandatory), send errors and warnings, and other messages. 

Components

I am considering the following components.
- reporter: a computing software with a need to report updates. Implements its functionality using the Odin library.
- server: the main Odin process
- viewer: any program that connects to the server to request information from reporters.
The advantage with separating server and viewer is that one could have several viewers connecting to the same server. For example, both my phone and my desktop could be viewing what the state on the server running on the desktop.
The server should not save a complete log, only the latest message from reporters, to avoid stacking up GiB of information. The whole system has to be light-weight. 

Addressing

A reporter has pid and a hostname which is used for identification. Each reporter may have additional labels for identifying its reporting and/or multiple progress/messaging needs. A label is a string, limited to some size.

Questions to ponder

- How do one best connect reporters, servers, and viewers?
- What kind of communication protocol (on top of TCP/IP or UDP) should be used? Plain text? Certain codes? JSON format?
- Maybe the easiest user interface would be to have a webbrowser? In that case, how would one communicate with the Odin server?
