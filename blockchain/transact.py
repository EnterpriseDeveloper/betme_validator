import os
import hashlib
import base64
import requests
import bech32

from dotenv import load_dotenv
from cosmospy import seed_to_privkey
from ecdsa import SigningKey, SECP256k1

from google.protobuf.any_pb2 import Any
from proto.bettery.events.v1.tx_pb2 import MsgValidateEvent
from proto.cosmos.tx.v1beta1.tx_pb2 import (
    TxBody,
    AuthInfo,
    SignerInfo,
    ModeInfo,
    SignDoc,
    TxRaw,
    Fee,
)
from proto.cosmos.crypto.secp256k1.keys_pb2 import PubKey
from proto.cosmos.base.v1beta1.coin_pb2 import Coin
from proto.cosmos.tx.signing.v1beta1.signing_pb2 import SignMode
from ecdsa.util import sigencode_string, sigdecode_string
from ecdsa.curves import SECP256k1

load_dotenv()

memo = os.environ.get("COSMOS_MEMO")
chainId = os.environ.get("COSMOS_CHAIN_ID")
apiUrl = os.environ.get("COSMOS_API_URL")

ADDRESS_PREFIX = "bettery"


# ================= SIGN =================

def sign_tx(privkey_bytes: bytes, sign_doc_bytes: bytes) -> bytes:
    sk = SigningKey.from_string(privkey_bytes, curve=SECP256k1)

    digest = hashlib.sha256(sign_doc_bytes).digest()

    signature = sk.sign_digest_deterministic(
        digest,
        sigencode=sigencode_string
    )

    r, s = sigdecode_string(signature, SECP256k1.order)

    # --- LOW S FIX ---
    if s > SECP256k1.order // 2:
        s = SECP256k1.order - s

    return sigencode_string(r, s, SECP256k1.order)


# ================= PUBKEY =================

def get_public_key(privkey_bytes: bytes) -> bytes:
    sk = SigningKey.from_string(privkey_bytes, curve=SECP256k1)
    vk = sk.get_verifying_key()

    x = vk.pubkey.point.x()
    y = vk.pubkey.point.y()

    prefix = b"\x02" if y % 2 == 0 else b"\x03"
    return prefix + x.to_bytes(32, byteorder="big")


# ================= ADDRESS =================

def get_creator_address(public_key_bytes: bytes) -> str:
    sha = hashlib.sha256(public_key_bytes).digest()
    ripemd = hashlib.new("ripemd160", sha).digest()

    return bech32.bech32_encode(
        ADDRESS_PREFIX,
        bech32.convertbits(ripemd, 8, 5)
    )


# ================= ACCOUNT QUERY =================

def get_sequence(address: str):
    res = requests.get(
        f"{apiUrl}/cosmos/auth/v1beta1/accounts/{address}"
    )
    data = res.json()

    # BaseAccount nested
    base = data["account"]

    account_number = int(base["account_number"])
    sequence = int(base["sequence"])

    return account_number, sequence


# ================= MAIN =================

def validate_event(eventId: int, answers: str, source: str):
    privkey_bytes = seed_to_privkey(memo)

    public_key_bytes = get_public_key(privkey_bytes)
    creator_address = get_creator_address(public_key_bytes)

    account_number, sequence = get_sequence(creator_address)

    # -------- Msg --------

    msg = MsgValidateEvent(
        creator=creator_address,
        event_id=eventId,
        answers=answers,
        source=source
    )

    any_msg = Any(
        type_url="/bettery.events.v1.MsgValidateEvent",
        value=msg.SerializeToString()
    )

    tx_body = TxBody(messages=[any_msg])
    body_bytes = tx_body.SerializeToString()

    # -------- PubKey --------

    pubkey = PubKey(key=public_key_bytes)

    any_pubkey = Any(
        type_url="/cosmos.crypto.secp256k1.PubKey",
        value=pubkey.SerializeToString()
    )

    signer_info = SignerInfo(
        public_key=any_pubkey,
        mode_info=ModeInfo(
            single=ModeInfo.Single(mode=SignMode.SIGN_MODE_DIRECT)
        ),
        sequence=sequence
    )

    # -------- Fee (FIXED) --------

    fee_coin = Coin(denom="ubet", amount="5000")

    fee = Fee(
        amount=[fee_coin],
        gas_limit=200000
    )

    auth_info = AuthInfo(
        signer_infos=[signer_info],
        fee=fee
    )

    auth_bytes = auth_info.SerializeToString()

    # -------- SignDoc --------

    sign_doc = SignDoc(
        body_bytes=body_bytes,
        auth_info_bytes=auth_bytes,
        chain_id=chainId,
        account_number=account_number
    )

    sign_doc_bytes = sign_doc.SerializeToString()
    # -------- Sign --------

    signature = sign_tx(privkey_bytes, sign_doc_bytes)

    # -------- TxRaw --------

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

    print("NODE RESPONSE:", res.json())
