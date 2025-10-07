import streamlit as st
from utils.gap_analysis_manager import GapAnalysisManager
from utils.sql_db_utils import SQLDatabaseUtils
from utils.default_patterns_manager import DefaultPatternsManager



class PatternSaver(GapAnalysisManager):
    def __init__(self, model_name, db_utils=None):
        super().__init__(model_name)
        self.db_utils = db_utils if db_utils else SQLDatabaseUtils()
        self.default_patterns_manager = DefaultPatternsManager()
        
    def save_patterns_to_database(self, selected_api_id):
        try:
            saved_count = 0
            
            for tag, pattern_data in st.session_state.pattern_responses.items():
                # Extract pattern data
                pattern_name = pattern_data['name']
                pattern_description = pattern_data['description']
                pattern_prompt = pattern_data['prompt']
                
                # Insert into api_section table
                api_section_last_inserted_id = self.db_utils.insert_data(
                    "api_section",
                    (selected_api_id, tag, tag),
                    columns=["api_id", "section_name", "section_display_name"]
                )
                
                # Insert into pattern_details table
                pattern_details_last_inserted_id = self.db_utils.insert_data(
                    "pattern_details",
                    (pattern_name, pattern_description, pattern_prompt),
                    columns=["pattern_name", "pattern_description", "pattern_prompt"]
                )
                
                # Insert into section_pattern_mapping table
                self.db_utils.insert_data(
                    "section_pattern_mapping",
                    (pattern_details_last_inserted_id, api_section_last_inserted_id, selected_api_id),
                    columns=["pattern_id", "section_id", "api_id"]
                )
                
                saved_count += 1

            # Enhanced success message with metrics
            st.markdown("""
            <div style="padding: 1rem; background: linear-gradient(135deg, rgba(16, 185, 129, 0.1), rgba(110, 231, 183, 0.1));
                        border-radius: 8px; border: 1px solid rgba(16, 185, 129, 0.3); margin: 1rem 0;">
                <h4 style="color: #065f46; margin: 0 0 0.5rem 0;">🎉 Database Save Successful!</h4>
                <p style="color: #047857; margin: 0;">Successfully saved <strong>{} patterns</strong> to the database with full schema mapping.</p>
                <div style="margin-top: 0.75rem; padding-top: 0.75rem; border-top: 1px solid rgba(16, 185, 129, 0.2);">
                    <small style="color: #059669;">
                        • API sections created: {}<br>
                        • Pattern details recorded: {}<br>
                        • Section mappings established: {}
                    </small>
                </div>
            </div>
            """.format(saved_count, saved_count, saved_count, saved_count), unsafe_allow_html=True)
            
        except Exception as e:
            st.markdown("""
            <div style="padding: 1rem; background: linear-gradient(135deg, rgba(239, 68, 68, 0.1), rgba(248, 113, 113, 0.1));
                        border-radius: 8px; border: 1px solid rgba(239, 68, 68, 0.3); margin: 1rem 0;">
                <h4 style="color: #7f1d1d; margin: 0 0 0.5rem 0;">❌ Database Save Failed</h4>
                <p style="color: #991b1b; margin: 0;">Error occurred while saving to database: <code>{}</code></p>
            </div>
            """.format(str(e)), unsafe_allow_html=True)
            raise e

    def save_patterns(self):
        try:
            if hasattr(st.session_state, 'pattern_responses') and st.session_state.pattern_responses:
                
                # Pattern summary metrics
                total_patterns = len(st.session_state.pattern_responses)
                verified_patterns = sum(1 for p in st.session_state.pattern_responses.values() if p.get('verified', False))
                
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("📊 Total Patterns", total_patterns, "extracted")
                with col2:
                    st.metric("✅ Verified", verified_patterns, "ready")
                with col3:
                    st.metric("⏳ Pending", total_patterns - verified_patterns, "verification")
                with col4:
                    completion_rate = f"{(verified_patterns/total_patterns*100):.0f}%" if total_patterns > 0 else "0%"
                    st.metric("🎯 Completion", completion_rate, "verified")
                
                st.markdown("---")
                
                # Save options with validation
                st.markdown("### 💾 Save to Personal Workspace")
                
                # Pre-save validation
                if verified_patterns == 0:
                    st.warning("⚠️ **Recommendation:** Verify at least one pattern before saving to ensure quality.")
                elif verified_patterns < total_patterns:
                    st.info(f"💭 **Notice:** {total_patterns - verified_patterns} patterns are unverified. You can still save them, but verification is recommended.")
                else:
                    st.success("✅ **All patterns verified!** Ready for database storage.")
                
                # API and Version Selection
                st.markdown("### 🎯 API Configuration")
                
                # API Management Section
                with st.expander("⚙️ Manage APIs", expanded=False):
                    st.markdown("**Add New API**")
                    st.info("💡 **Valid API Names:** LATAM, LH, LHG, AFKL (workspace names like 'LATAM_OVRS' are not allowed)")
                    
                    add_col1, add_col2 = st.columns([3, 1])
                    with add_col1:
                        new_api_name = st.text_input("API Name", placeholder="e.g., LATAM, LH, LHG, AFKL")
                    with add_col2:
                        # Validate API name before allowing addition
                        valid_api_names = ['LATAM', 'LH', 'LHG', 'AFKL']
                        is_valid_api = new_api_name.strip() in valid_api_names
                        
                        if st.button("➕ Add API", disabled=not new_api_name.strip() or not is_valid_api, key="add_new_api"):
                            try:
                                self.db_utils.run_query(
                                    "INSERT INTO api (api_name) VALUES (?)",
                                    (new_api_name.strip(),)
                                )
                                st.success(f"✅ Added API: {new_api_name}")
                                st.rerun()
                            except Exception as e:
                                st.error(f"❌ Failed to add API: {str(e)}")
                    
                    # Show validation message
                    if new_api_name.strip() and not is_valid_api:
                        st.warning(f"⚠️ '{new_api_name}' is not a valid API name. Use: LATAM, LH, LHG, or AFKL")
                    
                    st.markdown("**Delete Existing API**")
                    # Get APIs for deletion
                    delete_apis = self.db_utils.run_query("SELECT api_id, api_name FROM api ORDER BY api_name")
                    if delete_apis:
                        delete_col1, delete_col2 = st.columns([3, 1])
                        with delete_col1:
                            api_to_delete = st.selectbox(
                                "Select API to Delete",
                                options=[f"{api[1]} (ID: {api[0]})" for api in delete_apis],
                                key="delete_api_selector"
                            )
                        with delete_col2:
                            if st.button("🗑️ Delete", type="secondary", key="delete_selected_api"):
                                api_id = api_to_delete.split("(ID: ")[1].split(")")[0]
                                try:
                                    # Check if API has patterns
                                    patterns_count = self.db_utils.run_query(
                                        "SELECT COUNT(*) FROM patterns WHERE api_id = ?", (api_id,)
                                    )[0][0]
                                    
                                    if patterns_count > 0:
                                        st.warning(f"⚠️ Cannot delete API: {patterns_count} patterns are associated with it")
                                    else:
                                        self.db_utils.run_query("DELETE FROM api WHERE api_id = ?", (api_id,))
                                        st.success("✅ API deleted successfully")
                                        st.rerun()
                                except Exception as e:
                                    st.error(f"❌ Failed to delete API: {str(e)}")
                    else:
                        st.info("No APIs available to delete")
                
                # Get available APIs and filter out workspace names
                all_apis = self.db_utils.run_query("SELECT api_id, api_name FROM api ORDER BY api_name")
                
                # Filter to only include actual API names (not workspace names)
                valid_api_names = ['LATAM', 'LH', 'LHG', 'AFKL']  # Define actual API names
                apis = [(api_id, api_name) for api_id, api_name in all_apis if api_name in valid_api_names]
                
                if not apis:
                    st.warning("❌ No valid APIs found in database. Available APIs should be: LATAM, LH, LHG, AFKL")
                    st.info("💡 **Add missing APIs** using the 'Manage APIs' section above.")
                    
                    # Show current entries for debugging
                    if all_apis:
                        current_entries = [api[1] for api in all_apis]
                        st.info(f"📋 **Current database entries:** {', '.join(current_entries)}")
                        st.info("⚠️ **Note:** Workspace names like 'LATAM_OVRS' and 'Test Workspace' are not valid API names.")
                    return
                
                api_col1, api_col2 = st.columns(2)
                
                with api_col1:
                    # API selection dropdown with only valid APIs
                    api_options = {f"{api[1]}": api[0] for api in apis}
                    selected_api_name = st.selectbox(
                        "🏢 Select API",
                        options=list(api_options.keys()),
                        help="Choose the API to associate with these patterns (LATAM, LH, LHG, or AFKL)"
                    )
                    selected_api_id = api_options[selected_api_name]
                
                with api_col2:
                    # Get versions for selected API
                    versions = self.db_utils.run_query(
                        "SELECT version_number FROM apiversion WHERE api_id = ? ORDER BY version_number", 
                        (selected_api_id,)
                    )
                    
                    if versions:
                        version_options = [v[0] for v in versions]
                        selected_version = st.selectbox(
                            "📋 Select API Version",
                            options=version_options,
                            help=f"Choose the version for {selected_api_name}"
                        )
                    else:
                        st.warning(f"⚠️ No versions found for {selected_api_name}")
                        # Allow manual entry if no versions exist
                        selected_version = st.text_input(
                            "📝 Enter API Version",
                            placeholder="e.g., 17.2, 18.2, 21.3",
                            help="Enter the API version manually"
                        )
                        
                        if selected_version:
                            # Add the version to database if it doesn't exist
                            try:
                                self.db_utils.insert_api_version(selected_api_id, selected_version)
                                st.success(f"✅ Added new version {selected_version} for {selected_api_name}")
                            except Exception as e:
                                if "UNIQUE constraint failed" not in str(e):
                                    st.error(f"Error adding version: {e}")
                
                # Enhanced save section with pattern selection
                st.markdown("---")
                st.markdown("### 🎯 Select Patterns to Save")
                
                # Pattern selection interface
                available_patterns = st.session_state.pattern_responses
                selected_personal_patterns = {}
                
                # Bulk selection options
                bulk_col1, bulk_col2, bulk_col3 = st.columns([1, 1, 2])
                with bulk_col1:
                    select_all_personal = st.checkbox("Select All", key="select_all_personal")
                with bulk_col2:
                    select_verified_only = st.checkbox("Select Verified Only", key="select_verified_only_personal")
                with bulk_col3:
                    st.info("💡 Choose specific patterns to save to your personal workspace")
                
                st.markdown("---")
                
                # Individual pattern selection
                for i, (tag, pattern_data) in enumerate(available_patterns.items()):
                    col1, col2, col3 = st.columns([1, 3, 1])
                    
                    with col1:
                        # Auto-select logic
                        auto_select = False
                        if select_all_personal:
                            auto_select = True
                        elif select_verified_only and pattern_data.get('verified', False):
                            auto_select = True
                        
                        pattern_selected = st.checkbox(
                            "Save",
                            key=f"personal_pattern_{i}_{tag}",
                            value=auto_select,
                            help=f"Select to save '{pattern_data.get('name', tag)}' to personal workspace"
                        )
                    
                    with col2:
                        pattern_name = pattern_data.get('name', 'Unnamed Pattern')
                        pattern_desc = pattern_data.get('description', 'No description')
                        verified_status = "✅ Verified" if pattern_data.get('verified', False) else "⏳ Unverified"
                        
                        st.markdown(f"""
                        **{pattern_name}** ({verified_status})  
                        *{pattern_desc[:80]}{'...' if len(pattern_desc) > 80 else ''}*  
                        `{tag}`
                        """)
                    
                    with col3:
                        if pattern_data.get('verified', False):
                            st.success("Verified")
                        else:
                            st.warning("Unverified")
                    
                    if pattern_selected:
                        selected_personal_patterns[tag] = pattern_data
                
                # Summary section
                st.markdown("---")
                st.markdown("### 📊 Save Summary")
                
                save_col1, save_col2, save_col3 = st.columns([1, 1, 2])
                
                with save_col1:
                    st.metric("Selected Patterns", len(selected_personal_patterns))
                
                with save_col2:
                    selected_verified = sum(1 for p in selected_personal_patterns.values() if p.get('verified', False))
                    st.metric("Verified Selected", selected_verified)
                
                with save_col3:
                    st.markdown("**Target:**")
                    st.code(f"{selected_api_name} v{selected_version if selected_version else 'N/A'}", language=None)
                
                # Save button with enhanced styling
                st.markdown("")
                save_button_col1, save_button_col2 = st.columns([1, 2])
                
                # Check if API, version, and patterns are properly selected
                patterns_to_save = len(selected_personal_patterns)
                can_save = patterns_to_save > 0 and selected_version and selected_version.strip()
                
                with save_button_col1:
                    save_clicked = st.button(
                        f"💾 **Save {patterns_to_save} Selected Patterns**",
                        type="primary",
                        use_container_width=True,
                        disabled=not can_save,
                        help=f"Save {patterns_to_save} selected patterns to {selected_api_name} v{selected_version}" if can_save else "Select patterns, API and version first"
                    )
                
                with save_button_col2:
                    if can_save:
                        st.success(f"✅ Ready to save {patterns_to_save} selected patterns to {selected_api_name}")
                    elif patterns_to_save == 0:
                        st.warning("⚠️ No patterns selected to save")
                    else:
                        st.warning("⚠️ Please select API and version")
                
                # Process save operation
                if save_clicked and can_save:
                    with st.status(f"💾 **Saving {patterns_to_save} selected patterns to database...**", expanded=True) as status:
                        st.write("🔄 Preparing selected patterns for database storage...")
                        
                        # Use only the selected patterns
                        filtered_patterns = selected_personal_patterns
                        
                        # Temporarily update session state for saving
                        original_patterns = st.session_state.pattern_responses
                        st.session_state.pattern_responses = filtered_patterns
                        
                        try:
                            st.write(f"💾 Saving {len(filtered_patterns)} selected patterns to {selected_api_name} v{selected_version}...")
                            self.save_patterns_to_database(selected_api_id)
                            
                            st.write("✅ Database operations completed successfully!")
                            status.update(label=f"✅ **{len(filtered_patterns)} Selected Patterns Saved to {selected_api_name}!**", state="complete")
                            
                        except Exception as e:
                            st.write(f"❌ Error during save operation: {e}")
                            status.update(label="❌ **Save Operation Failed**", state="error")
                        finally:
                            # Restore original patterns
                            st.session_state.pattern_responses = original_patterns
                            
                # Save to shared workspace option
                st.markdown("---")
                st.markdown("### 📚 Save to Shared Workspace")
                st.markdown("Select specific patterns to save to the shared workspace for team collaboration.")
                
                # Get available patterns for selection
                available_patterns = st.session_state.pattern_responses if hasattr(st.session_state, 'pattern_responses') else {}
                
                if available_patterns:
                    # Pattern selection interface
                    st.markdown("#### 🎯 Select Patterns to Share")
                    
                    # Show patterns in a selectable format
                    selected_patterns = {}
                    
                    for i, (tag, pattern_data) in enumerate(available_patterns.items()):
                        col1, col2, col3 = st.columns([1, 3, 1])
                        
                        with col1:
                            pattern_selected = st.checkbox(
                                "Select",
                                key=f"shared_pattern_{i}_{tag}",
                                help=f"Select to save '{pattern_data.get('name', tag)}' to shared workspace"
                            )
                        
                        with col2:
                            pattern_name = pattern_data.get('name', 'Unnamed Pattern')
                            pattern_desc = pattern_data.get('description', 'No description')
                            verified_status = "✅ Verified" if pattern_data.get('verified', False) else "⏳ Unverified"
                            
                            st.markdown(f"""
                            **{pattern_name}** ({verified_status})  
                            *{pattern_desc[:80]}{'...' if len(pattern_desc) > 80 else ''}*  
                            `{tag}`
                            """)
                        
                        with col3:
                            if pattern_data.get('verified', False):
                                st.success("Ready")
                            else:
                                st.warning("Unverified")
                        
                        if pattern_selected:
                            selected_patterns[tag] = pattern_data
                    
                    # Category and API selection with predefined options
                    if selected_patterns:
                        st.markdown("---")
                        st.markdown("#### 📁 Choose Category and API Details")
                        
                        # Predefined categories with descriptions
                        category_options = {
                            "flight": "Flight segments, routes, and scheduling information",
                            "passenger": "Passenger details, names, and personal information", 
                            "fare": "Pricing, fare rules, and cost-related patterns",
                            "booking": "Booking references, confirmation codes, and reservations",
                            "airline": "Airline codes, carrier information, and airline-specific data",
                            "user_created": "Custom patterns created by users",
                            "custom": "Create a new category"
                        }
                        
                        col1, col2 = st.columns([1, 1])
                        
                        with col1:
                            selected_category_key = st.selectbox(
                                "Select category",
                                options=list(category_options.keys()),
                                format_func=lambda x: x.replace('_', ' ').title(),
                                help="Choose the most appropriate category for organization"
                            )
                        
                        with col2:
                            if selected_category_key == "custom":
                                custom_category = st.text_input(
                                    "Enter custom category name",
                                    placeholder="e.g., payment, security, validation",
                                    help="Create a new category for these patterns"
                                )
                                final_category = custom_category.strip().lower() if custom_category.strip() else "user_created"
                            else:
                                final_category = selected_category_key
                                st.info(f"💡 **{selected_category_key.replace('_', ' ').title()}**: {category_options[selected_category_key]}")
                        
                        # API and Version Selection for Shared Workspace
                        st.markdown("#### 🎯 API Configuration for Shared Workspace")
                        
                        # Get available APIs (same logic as personal workspace)
                        all_apis = self.db_utils.run_query("SELECT api_id, api_name FROM api ORDER BY api_name")
                        valid_api_names = ['LATAM', 'LH', 'LHG', 'AFKL']
                        apis = [(api_id, api_name) for api_id, api_name in all_apis if api_name in valid_api_names]
                        
                        if not apis:
                            st.warning("❌ No valid APIs found. Please add APIs (LATAM, LH, LHG, AFKL) from the personal workspace section above.")
                            shared_api_name = None
                            shared_api_version = None
                        else:
                            api_col1, api_col2 = st.columns(2)
                            
                            with api_col1:
                                # API selection dropdown with only valid APIs
                                api_options = {f"{api[1]}": api[0] for api in apis}
                                shared_api_name = st.selectbox(
                                    "🏢 Select API for Shared Workspace",
                                    options=list(api_options.keys()),
                                    help="Choose the API to associate with these shared patterns"
                                )
                                shared_api_id = api_options[shared_api_name]
                            
                            with api_col2:
                                # Get versions for selected API
                                versions = self.db_utils.run_query(
                                    "SELECT version_number FROM apiversion WHERE api_id = ? ORDER BY version_number", 
                                    (shared_api_id,)
                                )
                                
                                if versions:
                                    version_options = [v[0] for v in versions]
                                    shared_api_version = st.selectbox(
                                        "📋 Select API Version for Shared",
                                        options=version_options,
                                        help=f"Choose the version for {shared_api_name}"
                                    )
                                else:
                                    # Allow manual entry if no versions exist
                                    shared_api_version = st.text_input(
                                        "📝 Enter API Version for Shared",
                                        placeholder="e.g., 17.2, 18.2, 21.3",
                                        help="Enter the API version for shared workspace"
                                    )
                        
                        # Summary and save button
                        st.markdown("---")
                        st.markdown("#### 💾 Save Summary")
                        
                        col1, col2, col3, col4 = st.columns(4)
                        with col1:
                            st.metric("Selected Patterns", len(selected_patterns))
                        with col2:
                            verified_count = sum(1 for p in selected_patterns.values() if p.get('verified', False))
                            st.metric("Verified", verified_count)
                        with col3:
                            st.metric("Category", final_category.replace('_', ' ').title())
                        with col4:
                            if shared_api_name and shared_api_version:
                                st.metric("API Version", f"{shared_api_name} v{shared_api_version}")
                            else:
                                st.metric("API Version", "Not Selected")
                        
                        # Save to shared workspace button
                        can_save_shared = shared_api_name and shared_api_version and shared_api_version.strip()
                        save_shared_clicked = st.button(
                            f"🌐 Save {len(selected_patterns)} Patterns to Shared Workspace",
                            type="primary",
                            use_container_width=True,
                            disabled=not can_save_shared,
                            help=f"Save selected patterns to shared workspace under '{final_category}' category with {shared_api_name} v{shared_api_version}" if can_save_shared else "Please select API and version first"
                        )
                        
                        if save_shared_clicked and can_save_shared:
                            with st.status(f"💾 Saving {len(selected_patterns)} patterns to shared workspace...", expanded=True) as status:
                                st.write(f"📁 Saving to category: {final_category}")
                                st.write(f"🎯 API: {shared_api_name} v{shared_api_version}")
                                st.write(f"🔄 Processing {len(selected_patterns)} patterns...")
                                
                                try:
                                    self._save_to_default_library(selected_patterns, final_category, shared_api_name, shared_api_version)
                                    st.write("✅ Successfully saved to shared workspace!")
                                    status.update(label=f"✅ **{len(selected_patterns)} Patterns Saved to Shared Workspace!**", state="complete")
                                except Exception as e:
                                    st.write(f"❌ Error: {e}")
                                    status.update(label="❌ **Save to Shared Workspace Failed**", state="error")
                    
                    else:
                        st.info("📝 **Select patterns above** to save them to the shared workspace for team collaboration.")
                
                else:
                    st.info("📝 **No patterns available.** Extract patterns first to enable shared workspace saving.")
                
                # Additional database actions
                with st.expander("🔧 Advanced Operations", expanded=False):
                    st.markdown("""
                    <div style="padding: 0.75rem; background: rgba(59, 130, 246, 0.05); border-radius: 6px;">
                        <strong style="color: #1e40af;">📊 Database Features:</strong><br>
                        <span style="color: #6b7280; font-size: 0.9rem;">• Pattern versioning and tracking<br>
                        • Automatic duplicate detection<br>
                        • API section mapping<br>
                        • Cross-reference with existing patterns</span>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    if st.button("📄 Export Patterns as JSON", help="Download patterns as JSON file", key="export_patterns_json"):
                        import json
                        json_data = json.dumps(st.session_state.pattern_responses, indent=2)
                        st.download_button(
                            label="⬇️ Download JSON",
                            data=json_data,
                            file_name="extracted_patterns.json",
                            mime="application/json"
                        )
                    
                    if st.button("🗑️ Clear All Patterns", help="Remove all patterns from session", key="clear_all_patterns"):
                        if st.button("⚠️ Confirm Clear All", help="This action cannot be undone", key="confirm_clear_all"):
                            st.session_state.pattern_responses = {}
                            st.success("🧹 All patterns cleared from session")
                            st.rerun()
            else:
                # Enhanced empty state
                st.markdown("""
                <div style="text-align: center; padding: 3rem; margin: 2rem 0;
                            background: linear-gradient(135deg, rgba(107, 114, 128, 0.1), rgba(156, 163, 175, 0.1));
                            border-radius: 12px; border: 1px solid rgba(107, 114, 128, 0.3);">
                    <h3 style="color: #374151; margin: 0;">📋 No Patterns to Save</h3>
                    <p style="color: #6b7280; margin: 1rem 0;">Extract and verify patterns first to enable database saving.</p>
                    <div style="margin-top: 1.5rem;">
                        <p style="color: #6b7280; font-size: 0.9rem;">📝 Extract → ✅ Verify → 💾 Save → 🎉 Success</p>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
        except Exception as e:
            st.error(f"An error occurred while saving patterns: {e}")
            raise e
    
    def _save_to_default_library(self, patterns_dict: dict, category: str, api: str = None, api_version: str = None):
        """Save patterns to the default patterns library"""
        try:
            from core.database.default_patterns_manager import DefaultPattern
            from datetime import datetime
            
            saved_count = 0
            
            for tag, pattern_data in patterns_dict.items():
                # Skip patterns that are already from the default library
                if pattern_data.get('source') == 'default_library':
                    continue
                
                # Create a unique pattern ID
                pattern_id = f"user_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{tag.replace('/', '_').replace('[', '').replace(']', '')}"
                
                # Create DefaultPattern object
                default_pattern = DefaultPattern(
                    pattern_id=pattern_id,
                    name=pattern_data.get('name', f'User Pattern {tag}'),
                    description=pattern_data.get('description', ''),
                    prompt=pattern_data.get('prompt', ''),
                    example=pattern_data.get('example', ''),
                    xpath=pattern_data.get('path', tag),
                    category=category,
                    api=api,
                    api_version=api_version
                )
                
                if self.default_patterns_manager.save_pattern(default_pattern):
                    saved_count += 1
            
            if saved_count > 0:
                api_info = f" for {api} v{api_version}" if api and api_version else ""
                st.success(f"✅ Successfully saved {saved_count} patterns to shared workspace (category: {category}{api_info})")
            else:
                st.info("ℹ️ No new patterns were saved to shared workspace (existing default patterns skipped)")
                
        except Exception as e:
            st.error(f"Error saving patterns to default library: {e}")
            raise e