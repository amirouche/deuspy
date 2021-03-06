import ctypes
import six
import struct
import uuid
from bisect import bisect_left


_size_limits = tuple((1 << (i * 8)) - 1 for i in range(9))

# Define type codes:
NULL_CODE = 0x00
BYTES_CODE = 0x01
STRING_CODE = 0x02
NESTED_CODE = 0x05
INT_ZERO_CODE = 0x14
POS_INT_END = 0x1d
NEG_INT_START = 0x0b
FLOAT_CODE = 0x20
DOUBLE_CODE = 0x21
FALSE_CODE = 0x26
TRUE_CODE = 0x27
UUID_CODE = 0x30
VERSIONSTAMP_CODE = 0x33

# Reserved: Codes 0x03, 0x04, 0x23, and 0x24 are reserved for historical reasons.


def _find_terminator(v, pos):
    # Finds the start of the next terminator [\x00]![\xff] or the end of v
    while True:
        pos = v.find(b'\x00', pos)
        if pos < 0:
            return len(v)
        if pos + 1 == len(v) or v[pos + 1:pos + 2] != b'\xff':
            return pos
        pos += 2


# If encoding and sign bit is 1 (negative), flip all of the bits. Otherwise, just flip sign.
# If decoding and sign bit is 0 (negative), flip all of the bits. Otherwise, just flip sign.
def _float_adjust(v, encode):
    if encode and six.indexbytes(v, 0) & 0x80 != 0x00:
        return b''.join(map(lambda x: six.int2byte(x ^ 0xff), six.iterbytes(v)))
    elif not encode and six.indexbytes(v, 0) & 0x80 != 0x80:
        return b''.join(map(lambda x: six.int2byte(x ^ 0xff), six.iterbytes(v)))
    else:
        return six.int2byte(six.indexbytes(v, 0) ^ 0x80) + v[1:]


class SingleFloat(object):
    def __init__(self, value):
        if isinstance(value, float):
            # Restrict to the first 4 bytes (essentially)
            self.value = ctypes.c_float(value).value
        elif isinstance(value, ctypes.c_float):
            self.value = value.value
        elif isinstance(value, six.integertypes):
            self.value = ctypes.c_float(value).value
        else:
            raise ValueError("Incompatible type for single-precision float: " + repr(value))

    # Comparisons
    def __eq__(self, other):
        if isinstance(other, SingleFloat):
            return _compare_floats(self.value, other.value) == 0
        else:
            return False

    def __ne__(self, other):
        return not (self == other)

    def __lt__(self, other):
        return _compare_floats(self.value, other.value) < 0

    def __le__(self, other):
        return _compare_floats(self.value, other.value) <= 0

    def __gt__(self, other):
        return not (self <= other)

    def __ge__(self, other):
        return not (self < other)

    def __str__(self):
        return str(self.value)

    def __repr__(self):
        return "SingleFloat(" + str(self.value) + ")"

    def __hash__(self):
        # Left-circulate the child hash to make hash(self) != hash(self.value)
        v_hash = hash(self.value)
        if v_hash >= 0:
            return (v_hash >> 16) + ((v_hash & 0xFFFF) << 16)
        else:
            return ((v_hash >> 16) + 1) - ((abs(v_hash) & 0xFFFF) << 16)

    def __nonzero__(self):
        return bool(self.value)


class Versionstamp(object):
    LENGTH = 12
    _TR_VERSION_LEN = 10
    _MAX_USER_VERSION = (1 << 16) - 1
    _UNSET_TR_VERSION = 10 * six.int2byte(0xff)
    _STRUCT_FORMAT_STRING = '>' + str(_TR_VERSION_LEN) + 'sH'

    @classmethod
    def validate_tr_version(cls, tr_version):
        if tr_version is None:
            return
        if not isinstance(tr_version, bytes):
            msg = "Global version has illegal type {} (requires bytes)".format(type(tr_version))
            raise TypeError(msg)
        elif len(tr_version) != cls._TR_VERSION_LEN:
            msg = "Global version has incorrect length {} (requires {})"
            msg = msg.format(len(tr_version), cls._TR_VERSION_LEN)
            raise ValueError(msg)

    @classmethod
    def validate_user_version(cls, user_version):
        if not isinstance(user_version, six.integer_types):
            msg = "Local version has illegal type {} (requires integer type)"
            msg = msg.format(type(user_version))
            raise TypeError(msg)
        elif user_version < 0 or user_version > cls._MAX_USER_VERSION:
            msg = "Local version has value {} which is out of range"
            msg = msg.format(user_version)
            raise ValueError(msg)

    def __init__(self, tr_version=None, user_version=0):
        Versionstamp.validate_tr_version(tr_version)
        Versionstamp.validate_user_version(user_version)
        self.tr_version = tr_version
        self.user_version = user_version

    @staticmethod
    def incomplete(user_version=0):
        return Versionstamp(user_version=user_version)

    @classmethod
    def from_bytes(cls, v, start=0):
        if not isinstance(v, bytes):
            raise TypeError("Cannot parse versionstamp from non-byte string")
        elif len(v) - start < cls.LENGTH:
            msg = "Versionstamp byte string is too short (only {} bytes to read from"
            msg = msg.format(len(v) - start)
            raise ValueError(msg)
        else:
            tr_version = v[start:start + cls._TR_VERSION_LEN]
            if tr_version == cls._UNSET_TR_VERSION:
                tr_version = None
            user_version = (six.indexbytes(v, start + cls._TR_VERSION_LEN)
                            * (1 << 8)
                            + six.indexbytes(v, start + cls._TR_VERSION_LEN + 1))
            return Versionstamp(tr_version, user_version)

    def is_complete(self):
        return self.tr_version is not None

    def __repr__(self):
        return "<Versionstamp(" + repr(self.tr_version) + ", " + repr(self.user_version) + ")>"

    def to_bytes(self):
        return struct.pack(self._STRUCT_FORMAT_STRING,
                           self.tr_version if self.is_complete() else self._UNSET_TR_VERSION,
                           self.user_version)

    def completed(self, new_tr_version):
        if self.is_complete():
            raise RuntimeError("Versionstamp already completed")
        else:
            return Versionstamp(new_tr_version, self.user_version)

    def __eq__(self, other):
        if isinstance(other, Versionstamp):
            return (self.tr_version == other.tr_version
                    and self.user_version == other.user_version)
        else:
            return False

    def __ne__(self, other):
        return not (self == other)

    def __hash__(self):
        if self.tr_version is None:
            return hash(self.user_version)
        else:
            return hash(self.tr_version) * 37 ^ hash(self.user_version)

    def __nonzero__(self):
        return self.is_complete()


def _decode(v, pos):
    code = six.indexbytes(v, pos)
    if code == NULL_CODE:
        return None, pos + 1
    elif code == BYTES_CODE:
        end = _find_terminator(v, pos + 1)
        return v[pos + 1:end].replace(b"\x00\xFF", b"\x00"), end + 1
    elif code == STRING_CODE:
        end = _find_terminator(v, pos + 1)
        return v[pos + 1:end].replace(b"\x00\xFF", b"\x00").decode("utf-8"), end + 1
    elif code >= INT_ZERO_CODE and code < POS_INT_END:
        n = code - 20
        end = pos + 1 + n
        return struct.unpack(">Q", b'\x00' * (8 - n) + v[pos + 1:end])[0], end
    elif code > NEG_INT_START and code < INT_ZERO_CODE:
        n = 20 - code
        end = pos + 1 + n
        return struct.unpack(">Q", b'\x00' * (8 - n) + v[pos + 1:end])[0] - _size_limits[n], end
    elif code == POS_INT_END:  # 0x1d; Positive 9-255 byte integer
        length = six.indexbytes(v, pos + 1)
        val = 0
        for i in range(length):
            val = val << 8
            val += six.indexbytes(v, pos + 2 + i)
        return val, pos + 2 + length
    elif code == NEG_INT_START:  # 0x0b; Negative 9-255 byte integer
        length = six.indexbytes(v, pos + 1) ^ 0xff
        val = 0
        for i in range(length):
            val = val << 8
            val += six.indexbytes(v, pos + 2 + i)
        return val - (1 << (length * 8)) + 1, pos + 2 + length
    elif code == FLOAT_CODE:
        value = struct.unpack(">f", _float_adjust(v[pos + 1:pos + 5], False))
        return SingleFloat(value[0]), pos + 5
    elif code == DOUBLE_CODE:
        return struct.unpack(">d", _float_adjust(v[pos + 1:pos + 9], False))[0], pos + 9
    elif code == UUID_CODE:
        return uuid.UUID(bytes=v[pos + 1:pos + 17]), pos + 17
    elif code == FALSE_CODE:
        return False, pos + 1
    elif code == TRUE_CODE:
        return True, pos + 1
    elif code == VERSIONSTAMP_CODE:
        return Versionstamp.from_bytes(v, pos + 1), pos + 1 + Versionstamp.LENGTH
    elif code == NESTED_CODE:
        ret = []
        end_pos = pos + 1
        while end_pos < len(v):
            if six.indexbytes(v, end_pos) == 0x00:
                if end_pos + 1 < len(v) and six.indexbytes(v, end_pos + 1) == 0xff:
                    ret.append(None)
                    end_pos += 2
                else:
                    break
            else:
                val, end_pos = _decode(v, end_pos)
                ret.append(val)
        return tuple(ret), end_pos + 1
    else:
        raise ValueError("Unknown data type in DB: " + repr(v))


def _reduce_children(child_values):
    version_pos = -1
    len_so_far = 0
    bytes_list = []
    for child_bytes, child_pos in child_values:
        if child_pos >= 0:
            if version_pos >= 0:
                raise ValueError("Multiple incomplete versionstamps included in tuple")
            version_pos = len_so_far + child_pos
        len_so_far += len(child_bytes)
        bytes_list.append(child_bytes)
    return bytes_list, version_pos


def _encode(value, nested=False):
    # returns [code][data] (code != 0xFF)
    # encoded values are self-terminating
    # sorting need to work too!
    if value is None:
        if nested:
            return b''.join([six.int2byte(NULL_CODE), six.int2byte(0xff)]), -1
        else:
            return b''.join([six.int2byte(NULL_CODE)]), -1
    elif isinstance(value, bytes):  # also gets non-None fdb.impl.Value
        return six.int2byte(BYTES_CODE) + value.replace(b'\x00', b'\x00\xFF') + b'\x00', -1
    elif isinstance(value, six.text_type):
        code = six.int2byte(STRING_CODE)
        return code + value.encode('utf-8').replace(b'\x00', b'\x00\xFF') + b'\x00', -1
    elif isinstance(value, six.integer_types):
        if value == 0:
            return b''.join([six.int2byte(INT_ZERO_CODE)]), -1
        elif value > 0:
            if value >= _size_limits[-1]:
                length = (value.bit_length() + 7) // 8
                data = [six.int2byte(POS_INT_END), six.int2byte(length)]
                for i in range(length - 1, -1, -1):
                    data.append(six.int2byte((value >> (8 * i)) & 0xff))
                return b''.join(data), -1

            n = bisect_left(_size_limits, value)
            return six.int2byte(INT_ZERO_CODE + n) + struct.pack(">Q", value)[-n:], -1
        else:
            if -value >= _size_limits[-1]:
                length = (value.bit_length() + 7) // 8
                value += (1 << (length * 8)) - 1
                data = [six.int2byte(NEG_INT_START), six.int2byte(length ^ 0xff)]
                for i in range(length - 1, -1, -1):
                    data.append(six.int2byte((value >> (8 * i)) & 0xff))
                return b''.join(data), -1

            n = bisect_left(_size_limits, -value)
            maxv = _size_limits[n]
            return six.int2byte(INT_ZERO_CODE - n) + struct.pack(">Q", maxv + value)[-n:], -1
    elif isinstance(value, ctypes.c_float) or isinstance(value, SingleFloat):
        return six.int2byte(FLOAT_CODE) + _float_adjust(struct.pack(">f", value.value), True), -1
    elif isinstance(value, ctypes.c_double):
        return six.int2byte(DOUBLE_CODE) + _float_adjust(struct.pack(">d", value.value), True), -1
    elif isinstance(value, float):
        return six.int2byte(DOUBLE_CODE) + _float_adjust(struct.pack(">d", value), True), -1
    elif isinstance(value, uuid.UUID):
        return six.int2byte(UUID_CODE) + value.bytes, -1
    elif isinstance(value, bool):
        if value:
            return b''.join([six.int2byte(TRUE_CODE)]), -1
        else:
            return b''.join([six.int2byte(FALSE_CODE)]), -1
    elif isinstance(value, Versionstamp):
        version_pos = -1 if value.is_complete() else 1
        return six.int2byte(VERSIONSTAMP_CODE) + value.to_bytes(), version_pos
    elif isinstance(value, tuple) or isinstance(value, list):
        child_bytes, version_pos = _reduce_children(map(lambda x: _encode(x, True), value))
        new_version_pos = -1 if version_pos < 0 else version_pos + 1
        return b''.join([six.int2byte(NESTED_CODE)] + child_bytes + [six.int2byte(0x00)]), new_version_pos  # noqa
    else:
        raise ValueError("Unsupported data type: " + str(type(value)))


# packs the tuple possibly for versionstamp operations and returns the position of the
# incomplete versionstamp
#  * if there are no incomplete versionstamp members, this returns the packed tuple and -1
#  * if there is exactly one incomplete versionstamp member, it returns the tuple with the
#    two extra version bytes and the position of the version start
#  * if there is more than one incomplete versionstamp member, it throws an error
def _pack_maybe_with_versionstamp(t, prefix=None):
    if not isinstance(t, tuple):
        raise Exception("fdbtuple pack() expects a tuple, got a " + str(type(t)))

    bytes_list = [prefix] if prefix is not None else []

    child_bytes, version_pos = _reduce_children(map(_encode, t))
    if version_pos >= 0:
        version_pos += len(prefix) if prefix is not None else 0
        bytes_list.extend(child_bytes)
        bytes_list.append(struct.pack('<H', version_pos))
    else:
        bytes_list.extend(child_bytes)

    return b''.join(bytes_list), version_pos


# packs the specified tuple into a key
def pack(t, prefix=None):
    res, version_pos = _pack_maybe_with_versionstamp(t, prefix)
    if version_pos >= 0:
        raise ValueError("Incomplete versionstamp included in vanilla tuple pack")
    return res


# packs the specified tuple into a key for versionstamp operations
def pack_with_versionstamp(t, prefix=None):
    res, version_pos = _pack_maybe_with_versionstamp(t, prefix)
    if version_pos < 0:
        raise ValueError("No incomplete versionstamp included in tuple pack with versionstamp")
    return res


# unpacks the specified key into a tuple
def unpack(key, prefix_len=0):
    pos = prefix_len
    res = []
    while pos < len(key):
        r, pos = _decode(key, pos)
        res.append(r)
    return tuple(res)
