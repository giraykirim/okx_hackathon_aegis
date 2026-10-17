// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// @title AEGIS RiskDecisionRegistry (Avalanche Fuji C-Chain — Chain ID 43113)
/// @notice Stores sanitized canonical SHA-256 / Keccak-256 audit digests of off-chain AEGIS
///         pre-trade risk assessments and autonomous decisions.
/// @dev NONNEGOTIABLE BOUNDARY:
///      - Agent reasoning (EVREN), operational classification (LAYA), and OKX ATK observations
///        execute OFF-CHAIN.
///      - This contract stores ONLY cryptographic hashes (decisionHash, runIdHash,
///        policyVersionHash, caller, timestamp, verdictCode). No account credentials,
///        portfolio balances, or private customer inputs ever touch the EVM.
contract RiskDecisionRegistry {
    // Verdict codes: 1 = REVIEW, 2 = HALT, 3 = VETOED_NO_TRADE
    uint8 public constant VERDICT_REVIEW = 1;
    uint8 public constant VERDICT_HALT = 2;
    uint8 public constant VERDICT_VETOED_NO_TRADE = 3;

    struct DecisionReceipt {
        bytes32 decisionHash;       // Canonical SHA-256 digest of sanitized off-chain assessment/decision JSON
        bytes32 runIdHash;          // Hash of the off-chain run_id / assessment_id
        bytes32 policyVersionHash;  // Hash of the deterministic policy / schema version
        address caller;             // Authorized emitter address that anchored this receipt
        uint64 timestamp;           // Block timestamp on Avalanche Fuji C-Chain
        uint8 verdictCode;          // 1 = REVIEW, 2 = HALT, 3 = VETOED_NO_TRADE
    }

    address public owner;
    mapping(address => bool) public authorizedEmitters;
    mapping(bytes32 => DecisionReceipt) private _receipts;
    bytes32[] private _decisionHashes;

    event DecisionReceiptRecorded(
        bytes32 indexed decisionHash,
        bytes32 indexed runIdHash,
        bytes32 indexed policyVersionHash,
        address caller,
        uint64 timestamp,
        uint8 verdictCode
    );

    event EmitterAuthorizationChanged(address indexed emitter, bool authorized);
    event OwnershipTransferred(address indexed previousOwner, address indexed newOwner);

    error UnauthorizedCaller(address caller);
    error ZeroHashNotAllowed();
    error DuplicateDecisionHash(bytes32 decisionHash);
    error InvalidVerdictCode(uint8 verdictCode);
    error InvalidAddress();

    modifier onlyOwner() {
        if (msg.sender != owner) revert UnauthorizedCaller(msg.sender);
        _;
    }

    modifier onlyAuthorized() {
        if (!authorizedEmitters[msg.sender] && msg.sender != owner) {
            revert UnauthorizedCaller(msg.sender);
        }
        _;
    }

    constructor() {
        owner = msg.sender;
        authorizedEmitters[msg.sender] = true;
        emit OwnershipTransferred(address(0), msg.sender);
        emit EmitterAuthorizationChanged(msg.sender, true);
    }

    /// @notice Grant or revoke permission to record decision receipts.
    function setAuthorizedEmitter(address emitter, bool authorized) external onlyOwner {
        if (emitter == address(0)) revert InvalidAddress();
        authorizedEmitters[emitter] = authorized;
        emit EmitterAuthorizationChanged(emitter, authorized);
    }

    /// @notice Transfer contract ownership.
    function transferOwnership(address newOwner) external onlyOwner {
        if (newOwner == address(0)) revert InvalidAddress();
        address prev = owner;
        owner = newOwner;
        authorizedEmitters[newOwner] = true;
        emit OwnershipTransferred(prev, newOwner);
    }

    /// @notice Record a sanitized off-chain risk decision / assessment hash on Avalanche Fuji.
    /// @param decisionHash 32-byte SHA-256 digest of the canonicalized off-chain assessment/decision JSON
    /// @param runIdHash 32-byte digest of the off-chain run_id
    /// @param policyVersionHash 32-byte digest of the deterministic policy version (e.g. keccak256("aegis-policy-v2.0"))
    /// @param verdictCode 1 = REVIEW, 2 = HALT, 3 = VETOED_NO_TRADE
    function recordDecision(
        bytes32 decisionHash,
        bytes32 runIdHash,
        bytes32 policyVersionHash,
        uint8 verdictCode
    ) external onlyAuthorized {
        if (decisionHash == bytes32(0) || runIdHash == bytes32(0) || policyVersionHash == bytes32(0)) {
            revert ZeroHashNotAllowed();
        }
        if (_receipts[decisionHash].timestamp != 0) {
            revert DuplicateDecisionHash(decisionHash);
        }
        if (
            verdictCode != VERDICT_REVIEW &&
            verdictCode != VERDICT_HALT &&
            verdictCode != VERDICT_VETOED_NO_TRADE
        ) {
            revert InvalidVerdictCode(verdictCode);
        }

        uint64 ts = uint64(block.timestamp);
        _receipts[decisionHash] = DecisionReceipt({
            decisionHash: decisionHash,
            runIdHash: runIdHash,
            policyVersionHash: policyVersionHash,
            caller: msg.sender,
            timestamp: ts,
            verdictCode: verdictCode
        });
        _decisionHashes.push(decisionHash);

        emit DecisionReceiptRecorded(
            decisionHash,
            runIdHash,
            policyVersionHash,
            msg.sender,
            ts,
            verdictCode
        );
    }

    /// @notice Read back a recorded receipt by its decisionHash.
    function getDecisionReceipt(bytes32 decisionHash)
        external
        view
        returns (
            bytes32 storedDecisionHash,
            bytes32 runIdHash,
            bytes32 policyVersionHash,
            address caller,
            uint64 timestamp,
            uint8 verdictCode,
            bool exists
        )
    {
        DecisionReceipt storage r = _receipts[decisionHash];
        return (
            r.decisionHash,
            r.runIdHash,
            r.policyVersionHash,
            r.caller,
            r.timestamp,
            r.verdictCode,
            r.timestamp != 0
        );
    }

    /// @notice Total number of receipts committed to this registry.
    function totalReceipts() external view returns (uint256) {
        return _decisionHashes.length;
    }

    /// @notice Retrieve decisionHash at index `index`.
    function decisionHashAt(uint256 index) external view returns (bytes32) {
        return _decisionHashes[index];
    }
}
