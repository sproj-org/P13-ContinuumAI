# 🔍 Strict Dictionary-Based Column Mapping — R&D Summary

In this experiment, I explored a strict dictionary-based approach for automatically mapping user-provided CSV column names to our standardized sales schema. This method relies entirely on a predefined dictionary of aliases — essentially a manually curated list of all possible name variations a user may provide. The system checks whether each uploaded column name matches any alias in the dictionary, and if so, assigns it to the corresponding canonical field.

## ✅ Pros

- **Very fast and lightweight:** No ML model or API calls are required. The lookup is purely deterministic.  
- **Simple to implement and easy to debug:** The mapping logic is completely transparent, making it straightforward to trace errors.  
- **Zero dependency risk:** No reliance on LLM availability, latency, or cost.  

## ❌ Cons

- **Requires an extremely large dictionary:** Users can provide column names in thousands of unpredictable forms. Capturing all possible variations is unrealistic.  
- **Not robust to missing or slightly altered aliases:** A small deviation like `"OrderID"` vs `"order id"` can cause the entire mapping to fail.  
- **Does not generalize:** Any unseen variation will result in no mapping, causing gaps and potential downstream errors.  
- **High maintenance cost:** The alias dictionary needs constant updates as new datasets appear.  

## 🎯 Conclusion

Although this method is simple and fast, it is not suitable for our project. Our system must handle messy, inconsistent, user-generated files — and this approach collapses whenever a column name falls outside the predefined alias list. For real-world robustness, we require a more flexible solution such as an LLM-powered schema matcher or a hybrid fuzzy+ML approach.

This dictionary-based solution is valuable as a baseline, but it fails to meet the reliability requirements of our production pipeline and will not be used moving forward. We need a solution that takes into account the semantics of the strings as well.
