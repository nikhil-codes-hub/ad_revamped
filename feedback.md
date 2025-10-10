# AssistedDiscovery - Issues & Feedback

## Current Issues

### 1. Discovery Timeout When All Nodes Selected (2025-10-10)

**Issue:**
- Request timeout error when running Discovery after selecting all nodes in Node Manager
- Error message: "Request Timeout: The server took too long to respond"

**Root Cause:**
- When all nodes are selected, the system processes each node with individual LLM API calls
- With 50+ nodes, total processing time exceeds the timeout limit
- Frontend timeout was 5 minutes (300 seconds), backend LLM timeout 120 seconds per call

**Impact:**
- Discovery fails to complete for large XML files with many nodes
- User frustration during demo preparation

**Fix Applied:**
- ✅ Increased frontend timeout from 300s → 600s (10 minutes)
- ✅ Improved error messaging with troubleshooting steps
- ✅ Added guidance to select only critical nodes for faster processing

**Recommended Workaround:**
- In Node Manager, select only 5-8 critical nodes instead of all nodes
- Expected processing time: 2-3 minutes for selective extraction
- For OrderViewRS, recommended nodes:
  - Order, OrderItem, PassengerList, FlightSegment, BookingReferences, PriceDetail

**Long-term Solutions to Consider:**
- Batch LLM processing (process multiple nodes in single API call)
- Parallel processing with async workers
- Progress indicator with streaming updates
- Background job processing for large extractions
- Caching and incremental extraction

---

## Feature Requests

(Add feature requests here as they come)

---

## Performance Metrics

- **Discovery (all nodes):** 10+ minutes (exceeds timeout)
- **Discovery (5-8 nodes):** 2-3 minutes ✅
- **Identify workflow:** 30 seconds ✅
- **Pattern generation:** Included in Discovery time

---

## User Experience Improvements Needed

1. **Progress Indicator:** Show real-time progress during Discovery
2. **Estimated Time:** Display estimated completion time based on node count
3. **Cancellation:** Allow users to cancel long-running operations
4. **Background Processing:** Move long operations to background jobs

---

## Notes

- Frontend timeout change: `app_core.py` line 313
- All nodes now selected by default in Node Manager (per user request)
- System is production-ready for selective node extraction
