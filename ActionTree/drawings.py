# coding: utf8

# Copyright 2013-2015 Vincent Jacques <vincent@vincent-jacques.net>

import datetime

import graphviz
import matplotlib.dates
import matplotlib.figure as mpl

from . import Action


# @todo Capture last execution in an immutable copy of the action.
# Currently "a.execute(); r = make_report(a); a.execute()" will modify (and invalidate if timing changes a lot) the report.
# Same for Graph? Yes if we implement the Graph class as suggested in following todo.
# Adding a new dependency would be reflected in the graph after its creation.


def nearest(v, values):
    for i, value in enumerate(values):
        if v < value:
            break
    if i == 0:
        return values[0]
    else:
        assert values[i - 1] <= v < values[i], (i, values[i - 1], v, values[i])
        if v - values[i - 1] <= values[i] - v:
            return values[i - 1]
        else:
            return values[i]

intervals = [
    1, 2, 5, 10, 15, 30, 60,
    2 * 60, 10 * 60, 30 * 60, 3600,
    2 * 3600, 3 * 3600, 6 * 3600, 12 * 3600, 24 * 3600,
]


class ExecutionReport(object):
    def __init__(self, action):
        self.root_action = action
        self.actions = self.__sort_actions(action)
        self.begin_time = min(a.begin_time for a in self.actions)
        self.end_time = max(a.end_time for a in self.actions)
        self.duration = self.end_time - self.begin_time

    def __sort_actions(self, root):
        actions = []
        dependents = {}
        def walk(action):
            if action not in actions:
                actions.append(action)
                for d in action.dependencies:
                    dependents.setdefault(id(d), set()).add(id(action))
                    walk(d)
        walk(root)

        ordinates = {}
        def compute(action, ordinate):
            ordinates[id(action)] = ordinate
            for d in sorted(action.dependencies, key=lambda d: d.end_time):
                if len(dependents[id(d)]) == 1:
                    ordinate = compute(d, ordinate - 1)
                else:
                    dependents[id(d)].remove(id(action))
            return ordinate
        last_ordinate = compute(root, len(actions) - 1)

        assert last_ordinate == 0
        assert sorted(ordinates.values()) == range(len(actions))

        return sorted(actions, key=lambda a: ordinates[id(a)])
        # @todo Maybe count intersections and do a local search (two-three steps) to find if we can remove some of them.


def make_report(action):  # pragma no cover (Untestable? But small.)
    """
    Build a :class:`matplotlib.figure.Figure` about the execution of the action,
    showing successes and failures as well as timing information.

    See also :func:`.plot_report` if you want to draw the report on your own matplotlib figure.
    """
    fig = mpl.Figure()
    ax = fig.add_subplot(1, 1, 1)

    plot_report(action, ax)

    return fig


def plot_report(action, ax):
    """
    Plot a report about the execution of the action,
    showing successes and failures as well as timing information on the provided :class:`matplotlib.axes.Axes`.
    """
    report = ExecutionReport(action)

    ordinates = {id(a): len(report.actions) - i for i, a in enumerate(report.actions)}

    for a in report.actions:
        if a.status == Action.Successful:
            color = "blue"
        elif a.status == Action.Failed:
            color = "red"
        else:  # Canceled
            color = "gray"
        ax.plot([a.begin_time, a.end_time], [ordinates[id(a)], ordinates[id(a)]], color=color, lw=4)
        ax.annotate(str(a.label), xy=(a.begin_time, ordinates[id(a)]), xytext=(0, 3), textcoords="offset points")
        for d in a.dependencies:
            ax.plot([d.end_time, a.begin_time], [ordinates[id(d)], ordinates[id(a)]], "k:", lw=1)

    ax.get_yaxis().set_ticklabels([])
    ax.set_ylim(0.5, len(report.actions) + 1)

    min_time = report.begin_time.replace(microsecond=0)
    max_time = report.end_time.replace(microsecond=0) + datetime.timedelta(seconds=1)
    duration = int((max_time - min_time).total_seconds())

    ax.set_xlabel("Local time")
    ax.set_xlim(min_time, max_time)
    ax.xaxis_date()
    ax.xaxis.set_major_formatter(matplotlib.dates.DateFormatter("%H:%M:%S"))
    ax.xaxis.set_major_locator(matplotlib.dates.AutoDateLocator(maxticks=4, minticks=5))

    ax2 = ax.twiny()
    ax2.set_xlabel("Relative time")
    ax2.set_xlim(min_time, max_time)
    ticks = range(0, duration, nearest(duration // 5, intervals))
    ax2.xaxis.set_ticks([report.begin_time + datetime.timedelta(seconds=s) for s in ticks])
    ax2.xaxis.set_ticklabels(ticks)


class GraphBuilder(object):
    def __init__(self, action):
        self.__nodes = dict()
        self.__next_node = 0
        self.graph = graphviz.Digraph("action", node_attr={"shape": "box"})
        self.__create_node(action)

    def __create_node(self, a):
        if id(a) not in self.__nodes:
            node = str(self.__next_node)
            label = str(a.label)
            self.graph.node(node, label)
            self.__next_node += 1
            for d in a.dependencies:
                self.graph.edge(node, self.__create_node(d))
            self.__nodes[id(a)] = node
        return self.__nodes[id(a)]


# @todo Should there be a class Graph with a method get_graphviz_graph?
# This would allow implementing graphs in other libraries without creating more free functions.
# Same for execution reports.


def make_graph(action, format="png"):
    """
    Build a :class:`graphviz.Digraph` representing the action and its dependencies.
    """
    g = GraphBuilder(action).graph
    g.format = format
    return g
