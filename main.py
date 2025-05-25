#!/usr/bin/env python3

import logging

import kopf

from kubernetes.client import CoreV1Api, AppsV1Api, CustomObjectsApi
from kubernetes.config import load_kube_config, ConfigException, load_incluster_config


TIMEOUT_PERIOD = 90

LOG_LEVEL = logging.DEBUG

# LOG_FORMAT = "%(asctime)s%(msecs)d %(levelname)s: %(message)s"
LOG_FORMAT = "[%(asctime)s] %(levelname)s [%(name)s.%(funcName)s:%(lineno)d] %(message)s"


root_logger = logging.getLogger()
if len(root_logger.handlers) == 0:
    # Initialize the root logger only if it hasn't been done yet by a
    # parent module.
    logging.basicConfig(level=LOG_LEVEL, format=LOG_FORMAT, datefmt='%H:%M:%S')

logger = logging.getLogger("oauth2-proxy-controller")
logger.setLevel(LOG_LEVEL)


try:
    load_kube_config()
except ConfigException:
    load_incluster_config()

core_api = CoreV1Api()
apps_api = AppsV1Api()
custom_objects_api = CustomObjectsApi()


def _create_owner_reference_dict(name: str, uid: str) -> dict:
    return  {
        "apiVersion": "networking.k8s.io/v1",
        "kind": "Ingress",
        "blockOwnerDeletion": True,
        "controller": True,
        "name": name,
        "uid": uid
    }


def _create_gateway_dict(name: str, namespace: str, uid: str, host_name: str) -> dict:
    return {
        "apiVersion": "networking.istio.io/v1beta1",
        "kind": "Gateway",
        "metadata": {
            "name": f"temp-{name}-istio-ingress-gateway",
            "namespace": namespace,
            "ownerReferences": [
                _create_owner_reference_dict(name, uid)
            ]
        },
        "spec": {
            "selector": {
                "app": "istio-ingress"
            },
            "servers": [
                {
                    "port": {
                        "number": 80,
                        "name": "http",
                        "protocol": "HTTP"
                    },
                    "hosts": [host_name]
                }
            ]
        }
    }


def _create_virtual_service_dict(name: str, namespace: str, uid: str, host_name: str, destination_service: str, port: int, path: str) -> dict:
    return {
        "apiVersion": "networking.istio.io/v1beta1",
        "kind": "VirtualService",
        "metadata": {
            "name": f"temp-{name}-virtual-service",
            "namespace": namespace,
            "ownerReferences": [
                _create_owner_reference_dict(name, uid)
            ]
        },
        "spec": {
            "hosts": [host_name],
            "gateways": [f"temp-{name}-istio-ingress-gateway"],
            "http": [
                {
                    "route": [
                        {
                            "destination": {
                                "host": f"{destination_service}.istio-system.svc.cluster.local",
                                "port": {
                                    "number": port
                                }
                            }
                        }
                    ],
                    "match": [
                        {
                            "uri": {
                                "prefix": path
                            }
                        }
                    ]
                }
            ]
        }
    }


@kopf.on.create("networking.k8s.io", "v1", "Ingress")
def on_create(namespace, spec, body, **_kwargs) -> None:
    if ("spec" in body and "ingressClassName" in body["spec"] and body["spec"]["ingressClassName"] == "istio"
            and "metadata" in body and "labels" in body["metadata"] and "acme.cert-manager.io/http01-solver" in body["metadata"]["labels"]
            and body["metadata"]["labels"]["acme.cert-manager.io/http01-solver"] == "true"
    ):
        if "rules" in body["spec"]:
            name = body["metadata"]["name"]
            uid = body["metadata"]["uid"]
            rules = body["spec"]["rules"]
            hostname = rules[0]["host"]
            first_path = rules[0]["http"]["paths"][0]
            service_name = first_path["backend"]["service"]["name"]
            service_port = first_path["backend"]["service"]["port"]["number"]
            path = first_path["path"]

            logger.info(f"Got Ingress with host '{hostname}', service '{service_name}:{service_port}' on path '{path}'")
            logger.info(f"port type {type(service_port)}")

            gateway_dict = _create_gateway_dict(name, namespace, uid, hostname)
            virtual_service = _create_virtual_service_dict(name, namespace, uid, hostname, service_name, service_port, path)

            logger.info(f"Created gateway:\n{gateway_dict}")
            logger.info(f"Created virtualservice:\n{virtual_service}")

            custom_objects_api.create_namespaced_custom_object(
                group="networking.istio.io",
                version="v1beta1",
                plural="gateways",
                namespace=namespace,
                body=gateway_dict
            )
            custom_objects_api.create_namespaced_custom_object(
                group="networking.istio.io",
                version="v1beta1",
                plural="virtualservices",
                namespace=namespace,
                body=virtual_service
            )

        else:
            logger.error(f"No rules in 'spec'; {body}")
    else:
        logger.error(f"Unknown ingress; {body}")
