import os
import hashlib
from ecdsa import SigningKey, SECP256k1
from proto.bettery.events.v1.tx_pb2 import MsgValidateEvent
from google.protobuf.any_pb2 import Any
from proto.cosmos.tx.v1beta1.tx_pb2 import TxBody
from proto.cosmos.tx.v1beta1.tx_pb2 import AuthInfo, SignerInfo, ModeInfo
from proto.cosmos.crypto.secp256k1.keys_pb2 import PubKey
from proto.cosmos.base.v1beta1.coin_pb2 import Coin
from google.protobuf.any_pb2 import Any
from proto.cosmos.tx.v1beta1.tx_pb2 import SignDoc
from proto.cosmos.tx.v1beta1.tx_pb2 import TxRaw
import base64
import requests
from cosmospy import seed_to_privkey
from ecdsa import SigningKey, SECP256k1
import bech32


memo = os.environ.get("COSMOS_MEMO")
chainId = os.environ.get("COSMOS_CHAIN_ID")
apiUrl = os.environ.get("COSMOS_API_URL")


def sign_tx(privkey_hex: str, sign_doc_bytes: bytes) -> bytes:
    sk = SigningKey.from_string(bytes.fromhex(privkey_hex), curve=SECP256k1)
    return sk.sign_deterministic(sign_doc_bytes, hashfunc=hashlib.sha256)


def get_public_key(privkey_hex: str) -> bytes:
    sk = SigningKey.from_string(bytes.fromhex(privkey_hex), curve=SECP256k1)
    vk = sk.get_verifying_key()
    return b"\x02" + vk.to_string()[:32]


def get_creator_address(public_key_bytes: bytes) -> str:
    sha = hashlib.sha256(public_key_bytes).digest()

    ripemd = hashlib.new("ripemd160", sha).digest()

    return bech32.bech32_encode(
        "bettery",
        bech32.convertbits(ripemd, 8, 5)
    )


def get_sequence(creator_address: str):
    res = requests.get(
        f"{apiUrl}/cosmos/auth/v1beta1/accounts/{creator_address}"
    )
    data = res.json()
    account_number = int(data["account"]["base_account"]["account_number"])
    sequence = int(data["account"]["base_account"]["sequence"])
    return account_number, sequence


def validate_event(eventId: int, answers: str, source: str):
    privkey_hex = seed_to_privkey(memo)
    public_key_bytes = get_public_key(privkey_hex)
    creator_address = get_creator_address(public_key_bytes)
    account_number, sequence = get_sequence(creator_address)

    msg = MsgValidateEvent(
        creator=creator_address,
        event_id=eventId,
        answers=answers,
        source=source
    )

    any_msg = Any()
    any_msg.Pack(msg)

    tx_body = TxBody(
        messages=[any_msg],
        memo="validator"
    )

    body_bytes = tx_body.SerializeToString()

    pubkey = PubKey(key=public_key_bytes)

    any_pubkey = Any()
    any_pubkey.Pack(pubkey)

    signer_info = SignerInfo(
        public_key=any_pubkey,
        mode_info=ModeInfo(
            single=ModeInfo.Single(mode=1)  # SIGN_MODE_DIRECT
        ),
        sequence=sequence
    )

    fee = Coin(denom="ubet", amount="5000")

    auth_info = AuthInfo(
        signer_infos=[signer_info],
        fee={"amount": [fee], "gas_limit": 200000}
    )

    auth_bytes = auth_info.SerializeToString()

    sign_doc = SignDoc(
        body_bytes=body_bytes,
        auth_info_bytes=auth_bytes,
        chain_id=chainId,
        account_number=account_number
    )

    sign_doc_bytes = sign_doc.SerializeToString()
    signature = sign_tx(privkey_hex, sign_doc_bytes)
    tx_raw = TxRaw(
        body_bytes=body_bytes,
        auth_info_bytes=auth_bytes,
        signatures=[signature]
    )

    tx_bytes = base64.b64encode(tx_raw.SerializeToString()).decode()

    res = requests.post(
        f"{apiUrl}/cosmos/tx/v1beta1/txs",
        json={
            "tx_bytes": tx_bytes,
            "mode": "BROADCAST_MODE_SYNC"
        }
    )

    print(res.json())
