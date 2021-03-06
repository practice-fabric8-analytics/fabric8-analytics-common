"""API fuzzer logic."""

from fastlog import log

import json
import os
import itertools
import copy
import random

from setup import add_slash, yes_no, enabled_disabled
from rest_api_calls import send_payload
from test_result import TestResult

from random_payload_generator import RandomPayloadGenerator


def load_json(filename):
    """Load and decode JSON file."""
    with open(filename) as fin:
        return json.load(fin)


def fuzz(data):
    """Fuzz the payload."""
    rdg = RandomPayloadGenerator()
    new_key = rdg.generate_random_key_for_dict(data)
    new_data = rdg.generate_random_payload(restrict_types=(list, dict))
    print(new_key)
    print(new_data)


def construct_url(test):
    """Construct URL for the REST API call."""
    server_env_var = test["Server"]
    server_url = os.environ.get(server_env_var)
    if server_url is None:
        log.error("The following environment variable is not set {var}".format(var=server_env_var))
        return None

    url = "{base}{prefix}{method}".format(base=add_slash(server_url),
                                          prefix=add_slash(test["Prefix"]),
                                          method=test["Endpoint"])
    return url


def perform_test(url, http_method, dry_run, payload, cfg, expected_status, test, results):
    """Call the selected REST API with the autogenerated payload."""
    # pprint(payload)
    if dry_run:
        log.info("(dry run)")
        results.add_test_result(test, url, TestResult.DRY_RUN)
    else:
        if http_method == "POST":
            log.info("POSTing data")
            response = send_payload(url, payload, cfg["access_token"])
            status_code = response.status_code
            log.info("HTTP status code {code}".format(code=status_code))
            if status_code == expected_status:
                log.success("Success")
                results.add_test_result(test, url, TestResult.SUCCESS,
                                        status_code=status_code, payload=payload)
            else:
                log.error("Fail")
                results.add_test_result(test, url, TestResult.FAILURE,
                                        status_code=status_code, payload=payload)


def run_tests_with_removed_items_one_iteration(url, http_method, dry_run, original_payload,
                                               cfg, expected_status, items_count, remove_flags,
                                               test, results):
    """One iteration for the run_tests_with_removed_items()."""
    keys = list(original_payload.keys())
    # deep copy
    new_payload = copy.deepcopy(original_payload)
    for i in range(items_count):
        remove_flag = remove_flags[i]
        if remove_flag:
            key = keys[i]
            log.info("Removing item #{n} with key '{k}' from payload".format(n=i, k=key))
            del new_payload[key]
    perform_test(url, http_method, dry_run, new_payload, cfg, expected_status, test, results)


def run_tests_with_removed_items(url, http_method, dry_run, original_payload, cfg,
                                 expected_status, test, results):
    """Run tests with items removed from the original payload."""
    iteration = 0
    with log.indent():
        items_count = len(original_payload)
        # lexicographics ordering
        remove_flags_list = list(itertools.product([True, False], repeat=items_count))
        # the last item contains (False, False, False...) and we are not interested
        # in removing ZERO items
        remove_flags_list = remove_flags_list[:-1]

        with log.indent():
            log.info("Iteration #{n}".format(n=iteration))
            with log.indent():
                for remove_flags in remove_flags_list:
                    run_tests_with_removed_items_one_iteration(url, http_method, dry_run,
                                                               original_payload, cfg,
                                                               expected_status, items_count,
                                                               remove_flags, test, results)
            iteration += 1


def run_tests_with_added_items_one_iteration(url, http_method, dry_run, original_payload, cfg,
                                             expected_status, how_many, test, results):
    """One iteration for the run_tests_with_added_items()."""
    with log.indent():
        # deep copy
        new_payload = copy.deepcopy(original_payload)
        rpg = RandomPayloadGenerator()

        for i in range(how_many):
            log.info("Adding item #{n} into the payload".format(n=i))
            new_key = rpg.generate_random_key_for_dict(new_payload)
            new_value = rpg.generate_random_payload()
            new_payload[new_key] = new_value
        perform_test(url, http_method, dry_run, new_payload, cfg, expected_status, test, results)


def run_tests_with_changed_items_one_iteration(url, http_method, dry_run, original_payload, cfg,
                                               expected_status, how_many, test, results):
    """One iteration for the run_tests_with_changed_items()."""
    with log.indent():
        # deep copy
        new_payload = copy.deepcopy(original_payload)
        rpg = RandomPayloadGenerator()

        for i in range(0, how_many):
            log.info("Changing item #{n} in the payload".format(n=i))
            selected_key = random.choice(list(original_payload.keys()))
            new_value = rpg.generate_random_payload()
            new_payload[selected_key] = new_value
        perform_test(url, http_method, dry_run, new_payload, cfg, expected_status, test, results)


def run_tests_with_added_items(url, http_method, dry_run, original_payload, cfg, expected_status,
                               test, results):
    """Run tests with items added into the original payload."""
    with log.indent():
        iteration = 1
        # TODO: make it configurable
        for how_many in range(1, 4):
            for i in range(1, 4):
                with log.indent():
                    log.info("Iteration #{n}".format(n=iteration))
                    run_tests_with_added_items_one_iteration(url, http_method, dry_run,
                                                             original_payload, cfg,
                                                             expected_status, how_many,
                                                             test, results)
                    iteration += 1


def run_tests_with_changed_items(url, http_method, dry_run, original_payload, cfg, expected_status,
                                 test, results):
    """Run tests with items changed from the original payload."""
    with log.indent():
        iteration = 1
        for how_many in range(1, 1 + len(original_payload)):
            # TODO: make it configurable
            for i in range(1, 5):
                with log.indent():
                    log.info("Iteration #{n}".format(n=iteration))
                    run_tests_with_changed_items_one_iteration(url, http_method, dry_run,
                                                               original_payload, cfg,
                                                               expected_status, how_many,
                                                               test, results)
                    iteration += 1


def run_tests_with_mutated_items(url, http_method, dry_run, original_payload, cfg, expected_status,
                                 test, results):
    """Run tests with items mutated comparing to the original payload."""
    pass


def get_fuzzer_setting(fuzzer_settings, fuzzer_setting_name):
    """Read the fuzzer setting from the list of dict."""
    for fuzzer_setting in fuzzer_settings:
        if "Name" in fuzzer_setting and fuzzer_setting["Name"] == fuzzer_setting_name:
            return fuzzer_setting
    return None


def log_fuzzer_setting(fuzzer_setting):
    """Display basic information about fuzzer settings."""
    log.info("Fuzzer setting:")
    with log.indent():
        log.info("Iteration deep: " + fuzzer_setting["Iteration deep"])
        log.info("List length in range from {n} to {m}".format(
            n=fuzzer_setting["List min length"],
            m=fuzzer_setting["List max length"]))
        log.info("Dict length in range from {n} to {m}".format(
            n=fuzzer_setting["Dictionary min length"],
            m=fuzzer_setting["Dictionary max length"]))
        log.info("Dict keys length in range from {n} to {m}".format(
            n=fuzzer_setting["Min dictionary key length"],
            m=fuzzer_setting["Max dictionary key length"]))
        log.info("Strings length in range from {n} to {m}".format(
            n=fuzzer_setting["Min string length"],
            m=fuzzer_setting["Max string length"]))
        log.info("Dictionary characters:                  " +
                 fuzzer_setting["Dictionary characters"])
        log.info("String characters:                      " + fuzzer_setting["String characters"])
        log.info("Allow NaN in floats:                    " + fuzzer_setting["Allow NaN"])
        log.info("Allow Inf in floats:                    " + fuzzer_setting["Allow Inf"])
        log.info("Generate strings for SQL injection:     " +
                 fuzzer_setting["SQL injection strings"])
        log.info("Generate strings for Gremlin injection: " +
                 fuzzer_setting["Gremlin injection strings"])


def run_all_setup_tests(remove_items, add_items, change_types, mutate_payload,
                        url, http_method, dry_run, original_payload, cfg,
                        expected_status, test, results):
    """Run all tests that has been setup."""
    if remove_items:
        log.info("Run tests with items removed from original payload")
        run_tests_with_removed_items(url, http_method, dry_run, original_payload, cfg,
                                     expected_status, test, results)

    if add_items:
        log.info("Run tests with items added into the original payload")
        run_tests_with_added_items(url, http_method, dry_run, original_payload, cfg,
                                   expected_status, test, results)

    if change_types:
        log.info("Run tests with items changed from original payload")
        run_tests_with_changed_items(url, http_method, dry_run, original_payload, cfg,
                                     expected_status, test, results)

    if mutate_payload:
        log.info("Run tests with items mutated")
        run_tests_with_mutated_items(url, http_method, dry_run, original_payload, cfg,
                                     expected_status, test, results)


def run_test(cfg, fuzzer_settings, test, results):
    """Run one selected test."""
    url = construct_url(test)

    if url is None:
        results.add_test_result(test, None, TestResult.CONFIGURATION_ERROR,
                                cause="can not construct URL to API",
                                data=test["Prefix"])
        return

    log.info("URL to test:                " + url)

    http_method = test["Method"]
    log.info("HTTP method:                " + http_method)

    expected_status = int(test["Expected status"])
    log.info("Expected HTTP status:       " + str(expected_status))

    dry_run = cfg["dry_run"]
    add_items = yes_no(test["Add items"])
    remove_items = yes_no(test["Remove items"])
    change_types = yes_no(test["Change types"])
    mutate_payload = yes_no(test["Mutate payload"])
    filename = test["Payload"]

    fuzzer_setting_name = test["Fuzzer setting"]

    log.info("Add items operation:        " + enabled_disabled(add_items))
    log.info("Remove items operation:     " + enabled_disabled(remove_items))
    log.info("Change item type operation: " + enabled_disabled(change_types))
    log.info("Mutate payload operation:   " + enabled_disabled(mutate_payload))
    log.info("Original payload file:      " + filename)
    log.info("Fuzzer setting name:        " + fuzzer_setting_name)

    fuzzer_setting = get_fuzzer_setting(fuzzer_settings, fuzzer_setting_name)

    if fuzzer_setting_name is None:
        log.error("Test configuration error: fuzzer setting does not exist")
        results.add_test_result(test, None, TestResult.CONFIGURATION_ERROR,
                                cause="fuzzer setting does not exist", data=fuzzer_setting_name)
        return

    log_fuzzer_setting(fuzzer_setting)

    try:
        original_payload = load_json(filename)
    except Exception:
        # JSON does not exist or can't be decoded
        results.add_test_result(test, None, TestResult.CONFIGURATION_ERROR,
                                cause="cannot load JSON payload", data=filename)
        return

    # test whether user configured just regular REST API call test
    if not any([add_items, remove_items, change_types, mutate_payload]):
        # run the test with the original payload, that won't be altered in any way
        perform_test(url, http_method, dry_run, original_payload, cfg, expected_status, test,
                     results)

    run_all_setup_tests(remove_items, add_items, change_types, mutate_payload,
                        url, http_method, dry_run, original_payload, cfg,
                        expected_status, test, results)

    log.success("Finished")
    return
