import os
import grpc
from proto.bettery.events.v1 import query_pb2, query_pb2_grpc

from dotenv import load_dotenv
load_dotenv()


def fetch_events():
    url = os.environ.get("COSMOS_RPC_URL")
    channel = grpc.insecure_channel(url)
    stub = query_pb2_grpc.QueryStub(channel)
    request = query_pb2.QueryAllEventsRequest()
    response = stub.ListEventsForValidator(request)
    return response.events
