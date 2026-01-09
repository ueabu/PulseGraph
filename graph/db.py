from __future__ import annotations

import os
from neo4j import GraphDatabase, Driver

def get_neo4j_driver() -> Driver:
    uri = os.getenv("NEO4J_URI")
    user = os.getenv("NEO4J_USER")
    password = os.getenv("NEO4J_PASSWORD")  # change locally if needed
    return GraphDatabase.driver(uri, auth=(user, password))