"""Генерируемые проверки кадра, JSON и ошибок протокола."""

import struct

import pytest
from hypothesis import given, strategies as st

from src import protocol

JSON = st.recursive(
    st.one_of(st.none(), st.booleans(), st.integers(), st.text()),
    lambda children: st.one_of(st.lists(children, max_size=5),
                              st.dictionaries(st.text(), children,
                                              max_size=5)),
    max_leaves=15,
)


@given(operation=st.sampled_from(list(protocol.Operation)),
       arguments=st.dictionaries(st.text(), JSON, max_size=5))
def test_request_layout(operation, arguments):
    frame = protocol.encode_request(operation, arguments)
    body = frame[6:]
    assert frame[:4] == len(body).to_bytes(4, "little")
    assert frame[4:6] == int(operation).to_bytes(2, "little")
    assert protocol.decode_request_header(frame[:6]) == (operation,
                                                        len(body))
    assert protocol.parse_request(body) == arguments


@given(operation=st.sampled_from(list(protocol.Operation)), value=JSON)
def test_response_layout(operation, value):
    body = protocol.result_body(value)
    frame = protocol.encode_response(operation, body)
    assert frame[:1] == int(operation).to_bytes(1, "little")
    assert frame[1:5] == len(body).to_bytes(4, "little")
    assert protocol.decode_response_header(frame[:5]) == (len(body),
                                                         int(operation))
    assert protocol.parse_response(frame[5:]) == value


@given(kind=st.sampled_from(list(protocol.ERRORS.values())), text=st.text())
def test_error_roundtrip(kind, text):
    with pytest.raises(kind) as error:
        protocol.parse_response(protocol.error_body(kind(text)))
    assert str(error.value) == text


@given(code=st.integers(min_value=14, max_value=65535))
def test_unknown_operation(code):
    with pytest.raises(protocol.ProtocolError):
        protocol.decode_request_header(struct.pack("<IH", 0, code))


@given(size=st.integers(min_value=protocol.MAX_BODY + 1,
                      max_value=4294967295))
def test_oversized_header(size):
    with pytest.raises(protocol.ProtocolError):
        protocol.decode_request_header(struct.pack("<IH", size, 1))
    with pytest.raises(protocol.ProtocolError):
        protocol.decode_response_header(struct.pack("<BI", 1, size))


@given(body=st.sampled_from([
    b"{", b"\xff", b"[]", b"null", b'{"x":NaN}', b'{"x":1,"x":2}',
]))
def test_bad_request(body):
    with pytest.raises(protocol.ProtocolError):
        protocol.parse_request(body)


@given(body=st.sampled_from([
    b"[]", b"{}", b'{"status":"ok"}', b'{"status":"unknown"}',
    b'{"status":"error","type":"Unknown","message":"x"}',
    b'{"status":"error","type":"ValidationError","message":0}',
]))
def test_bad_response(body):
    with pytest.raises(protocol.ProtocolError):
        protocol.parse_response(body)


@given(header=st.binary(max_size=4))
def test_short_headers(header):
    for decode in (protocol.decode_request_header,
                   protocol.decode_response_header):
        with pytest.raises(protocol.ProtocolError):
            decode(header)
