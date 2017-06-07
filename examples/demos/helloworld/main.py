import bonobo

def get_graph():
    graph = bonobo.Graph(
        range(42),
        bonobo.Filter(filter=lambda x: x % 2),
        print,
    )

    return graph

graph = get_graph()

if __name__ == '__main__':
    from bonobo.commands.run import get_default_services
    bonobo.run(graph, services=get_default_services(__file__))

