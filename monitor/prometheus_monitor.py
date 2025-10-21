from prometheus_client import Counter, Histogram
from flask import request
import time
import functools

# define metrics
REQUEST_COUNT = Counter(
    'http_requests_total',
    'HTTP Requests Total',
    ['method', 'endpoint', 'status_code']
)

REQUEST_FAILURES = Counter(
    'http_requests_failures_total',
    'HTTP Requests Failures Total',
    ['method', 'endpoint', 'error_type']
)

REQUEST_DURATION = Histogram(
    'http_request_duration_seconds',
    'HTTP Request Duration',
    ['method', 'endpoint', 'status_code']
)

# business failures counter
BUSINESS_FAILURES = Counter(
    'business_logic_failures_total',
    'Business Logic Failures Total',
    ['endpoint', 'failure_type', 'reason']
)


def monitor_requests(endpoint=None):
    """http request monitor"""

    def decorator(f):
        @functools.wraps(f)
        def wrapped(*args, **kwargs):
            # dynamic get entry point
            actual_endpoint = endpoint or request.path
            method = request.method
            start_time = time.time()

            try:
                response = f(*args, **kwargs)

                # get status code
                if hasattr(response, 'status_code'):
                    status_code = response.status_code
                elif isinstance(response, tuple) and len(response) == 2:
                    status_code = response[1]
                else:
                    status_code = 200

                # record request
                REQUEST_COUNT.labels(
                    method=method,
                    endpoint=actual_endpoint,
                    status_code=status_code
                ).inc()

                # record duration
                REQUEST_DURATION.labels(
                    method=method,
                    endpoint=actual_endpoint,
                    status_code=status_code
                ).observe(time.time() - start_time)

                # judge failure
                if status_code >= 400:
                    REQUEST_FAILURES.labels(
                        method=method,
                        endpoint=actual_endpoint,
                        error_type=f'http_{status_code}'
                    ).inc()

                return response

            except Exception as e:
                # record exception
                error_type = type(e).__name__
                REQUEST_FAILURES.labels(
                    method=method,
                    endpoint=actual_endpoint,
                    error_type=error_type
                ).inc()

                REQUEST_COUNT.labels(
                    method=method,
                    endpoint=actual_endpoint,
                    status_code='500'
                ).inc()

                # reraise
                raise

        return wrapped

    return decorator


def record_business_failure(endpoint, failure_type, reason):
    BUSINESS_FAILURES.labels(
        endpoint=endpoint,
        failure_type=failure_type,
        reason=reason
    ).inc()
