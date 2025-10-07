import json
import streamlit as st
from core.assisted_discovery.gap_analysis_manager import GapAnalysisManager
from core.prompts_manager.gap_analysis_prompt_manager import GapAnalysisPromptManager

class PatternVerifier(GapAnalysisManager, GapAnalysisPromptManager):
    def __init__(self, model_name):
        super().__init__(model_name)
        
    def verify_prompts(self):
        if st.session_state.pattern_responses:
            st.session_state.is_verified = False
            
            # Enhanced pattern selection
            col1, col2 = st.columns([2, 1])
            with col1:
                selected_tag = st.selectbox(
                    "🎯 Select Pattern to Verify", 
                    list(st.session_state.pattern_responses.keys()), 
                    key="tag_selector", 
                    index=0,
                    help="Choose a pattern from your extracted collection"
                )
            with col2:
                total_patterns = len(st.session_state.pattern_responses)
                verified_count = sum(1 for p in st.session_state.pattern_responses.values() if p.get('verified', False))
                st.metric("Progress", f"{verified_count}/{total_patterns}", "verified")
            
            st.session_state.verification_response = None
            
            if selected_tag:
                # Get pattern data from session state
                pattern_data = st.session_state.pattern_responses[selected_tag]
                pattern_name = pattern_data['name']
                pattern_description = pattern_data['description']
                pattern_prompt = pattern_data['prompt']
                is_verified = pattern_data.get('verified', False)
                
                st.markdown("---")
                
                # Enhanced pattern information display
                st.markdown("### 📋 Pattern Details")
                
                # Status indicator
                status_col1, status_col2 = st.columns([3, 1])
                with status_col1:
                    st.markdown(f"**Selected Pattern:** `{selected_tag}`")
                with status_col2:
                    if is_verified:
                        st.success("✅ Verified")
                    else:
                        st.warning("⏳ Pending")
                
                # Pattern information in enhanced cards
                with st.container():
                    st.markdown("""
                    <div style="background: linear-gradient(135deg, rgba(16, 185, 129, 0.05), rgba(59, 130, 246, 0.05));
                                padding: 1rem; border-radius: 8px; margin: 0.5rem 0; border-left: 4px solid #10b981;">
                        <strong style="color: #065f46;">📛 Pattern Name:</strong><br>
                        <code style="background: white; padding: 0.25rem 0.5rem; border-radius: 4px;">{}</code>
                    </div>
                    """.format(pattern_name), unsafe_allow_html=True)
                    
                    st.markdown("""
                    <div style="background: linear-gradient(135deg, rgba(59, 130, 246, 0.05), rgba(147, 197, 253, 0.05));
                                padding: 1rem; border-radius: 8px; margin: 0.5rem 0; border-left: 4px solid #3b82f6;">
                        <strong style="color: #1e40af;">📝 Description:</strong><br>
                        <div style="background: white; padding: 0.5rem; border-radius: 4px; margin-top: 0.5rem;">{}</div>
                    </div>
                    """.format(pattern_description), unsafe_allow_html=True)
                    
                    with st.expander("🔧 View Generated Prompt", expanded=False):
                        st.code(pattern_prompt, language='text')
                
                # Add pattern improvement options
                self.improve_or_overwrite_prompt(selected_tag, pattern_name, pattern_description, pattern_prompt)
                
                st.markdown("---")
                
                # Enhanced XML verification section
                st.markdown("### 🧪 XML Verification Test")
                st.info("💡 **Tip:** Paste a sample XML snippet that should match this pattern to verify its accuracy.")
                
                xml_content = st.text_area(
                    "XML Test Content", 
                    height=120,
                    help="Enter XML content to test against this pattern",
                    placeholder="<sample>\n  <element>value</element>\n</sample>"
                )
                
                verify_col1, verify_col2 = st.columns([1, 3])
                with verify_col1:
                    verify_clicked = st.button(
                        "🚀 Verify Pattern", 
                        key="verifier_submit",
                        disabled=not xml_content.strip(),
                        type="primary",
                        use_container_width=True
                    )
                
                if verify_clicked and xml_content.strip():
                    with st.status("🔄 **Verifying Pattern...**", expanded=True) as status:
                        st.write("🧪 Testing XML against pattern...")
                        response = self.verify_xml_with_generated_prompt(xml_content, pattern_prompt)
                        response_json = json.loads(response)
                        confirmation = response_json.get('confirmation', 'No confirmation provided')
                        # Handle both boolean and string values for is_confirmed
                        is_confirmed_value = response_json.get('is_confirmed', False)
                        if isinstance(is_confirmed_value, str):
                            is_verified = is_confirmed_value.lower() == 'true'
                        else:
                            is_verified = bool(is_confirmed_value)
                        st.session_state.verification_response = confirmation
                        st.session_state.is_verified = is_verified
                        
                        # Update pattern data with verification status, preserving existing fields
                        existing_pattern = st.session_state.pattern_responses[selected_tag]
                        if isinstance(existing_pattern, dict):
                            # Update existing dictionary while preserving all fields
                            existing_pattern.update({
                                'verified': is_verified,
                                'verification_reason': confirmation
                            })
                        else:
                            # Handle old list format by converting to new format with all required fields
                            st.session_state.pattern_responses[selected_tag] = {
                                'name': pattern_name,
                                'path': selected_tag,
                                'description': pattern_description,
                                'prompt': pattern_prompt,
                                'example': existing_pattern[4] if len(existing_pattern) > 4 else 'N/A',
                                'verified': is_verified,
                                'verification_reason': confirmation
                            }
                        
                        if is_verified:
                            st.write("✅ Verification successful!")
                            status.update(label="✅ **Verification Complete!**", state="complete")
                        else:
                            st.write("❌ Verification failed.")
                            status.update(label="❌ **Verification Failed**", state="error")
        else:
            # Enhanced empty state
            st.markdown("""
            <div style="text-align: center; padding: 3rem; margin: 2rem 0;
                        background: linear-gradient(135deg, rgba(245, 158, 11, 0.1), rgba(252, 211, 77, 0.1));
                        border-radius: 12px; border: 1px solid rgba(245, 158, 11, 0.3);">
                <h3 style="color: #92400e; margin: 0;">⚠️ No Patterns Available</h3>
                <p style="color: #6b7280; margin: 1rem 0 0 0;">Please extract patterns first using the <strong>Extract Patterns</strong> tab.</p>
                <div style="margin-top: 1.5rem;">
                    <p style="color: #6b7280; font-size: 0.9rem;">📝 Upload XML → 🤖 Extract Patterns → ✅ Verify → 💾 Save</p>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
        # Enhanced verification results display
        if 'verification_response' in st.session_state and st.session_state.verification_response is not None:
            st.markdown("---")
            st.markdown("### 📊 Verification Results")
            
            if st.session_state.is_verified:
                # HTML-escape the verification response to prevent XML tags from being interpreted as HTML
                escaped_response = st.session_state.verification_response.replace('<', '&lt;').replace('>', '&gt;')
                st.markdown("""
                <div style="padding: 1rem; background: linear-gradient(135deg, rgba(16, 185, 129, 0.1), rgba(110, 231, 183, 0.1));
                            border-radius: 8px; border: 1px solid rgba(16, 185, 129, 0.3); margin: 0.5rem 0;">
                    <h4 style="color: #065f46; margin: 0 0 0.5rem 0;">✅ Verification Successful</h4>
                    <p style="color: #047857; margin: 0;">{}</p>
                </div>
                """.format(escaped_response), unsafe_allow_html=True)
            else:
                # HTML-escape the verification response to prevent XML tags from being interpreted as HTML
                escaped_response = st.session_state.verification_response.replace('<', '&lt;').replace('>', '&gt;')
                st.markdown("""
                <div style="padding: 1rem; background: linear-gradient(135deg, rgba(239, 68, 68, 0.1), rgba(248, 113, 113, 0.1));
                            border-radius: 8px; border: 1px solid rgba(239, 68, 68, 0.3); margin: 0.5rem 0;">
                    <h4 style="color: #7f1d1d; margin: 0 0 0.5rem 0;">❌ Verification Failed</h4>
                    <p style="color: #991b1b; margin: 0;">{}</p>
                </div>
                """.format(escaped_response), unsafe_allow_html=True)

    def verify_xml_with_generated_prompt(self, xml_content, selected_prompt):
        """
        Verifies XML content with a generated prompt.

        Args:
            xml_content (str): The XML content to verify.
            selected_prompt (str): The prompt to use for verification.

        Returns:
            str: The raw JSON content returned by the agent.

        Raises:
            FileNotFoundError: If the prompt file is not found.
            ValueError: If the response from the agent is invalid or cannot be parsed.
        """
        try:
            conversational_params = {
                "xml_content": xml_content,
                "selected_prompt": selected_prompt,
            }
            self.load_prompts_for_pattern_verfication(conversational_params)

            # Use a spinner to indicate processing
            with st.spinner("Verifying the XML with the given prompt..."):
                # Get the response from the agent
                raw_content = self._initiate_conversation()

                # Handle cases where the response starts with "json" or is wrapped in code blocks
                if raw_content.startswith("json\n") or raw_content.startswith("```json\n"):
                    raw_content = raw_content[raw_content.index("{"):]
                raw_content = raw_content.rstrip("```")

                return raw_content

        except FileNotFoundError as e:
            st.error(f"File error: {e}")
            raise
        except ValueError as e:
            st.error(f"Response error: {e}")
            raise
        except KeyError as e:
            st.error(f"Key error in response: {e}")
            raise
        except Exception as e:
            st.error(f"An unexpected error occurred: {e}")
            raise

    def improve_or_overwrite_prompt(self, selected_tag, pattern_name, pattern_description, pattern_prompt):
        with st.expander("🔧 Advanced: Improve Pattern Prompt", expanded=False):
            st.markdown("""
            <div style="padding: 0.75rem; background: rgba(59, 130, 246, 0.05); border-radius: 6px; margin-bottom: 1rem;">
                <strong style="color: #1e40af;">💡 Improvement Options:</strong><br>
                <span style="color: #6b7280; font-size: 0.9rem;">Enhance the Genie prompt for better pattern recognition accuracy</span>
            </div>
            """, unsafe_allow_html=True)
            
            regen_radio = st.radio(
                "🎯 Choose improvement method:", 
                ["Keep current prompt", "Enhance with hints", "Complete rewrite"],
                help="Select how you want to modify the pattern prompt"
            )
            
            if regen_radio != "Keep current prompt":
                if regen_radio == "Enhance with hints":
                    st.markdown("**🔍 Enhancement Mode:** Add hints to improve the existing prompt")
                    hints = st.text_area(
                        "Improvement hints", 
                        height=100,
                        help="Provide specific hints to make the prompt more accurate",
                        placeholder="e.g., Focus on specific attributes, handle edge cases, improve validation..."
                    )
                    overwrite_mode = False
                else:  # Complete rewrite
                    st.markdown("**⚠️ Rewrite Mode:** Replace the entire prompt with your custom version")
                    hints = st.text_area(
                        "New prompt content", 
                        height=100,
                        help="Write a completely new prompt to replace the current one",
                        placeholder="Write your custom prompt here..."
                    )
                    overwrite_mode = True
                
                improve_col1, improve_col2 = st.columns([1, 2])
                with improve_col1:
                    if st.button(
                        "🚀 Apply Changes", 
                        disabled=not hints.strip(),
                        type="primary",
                        use_container_width=True
                    ):
                        if overwrite_mode:
                            self.overwrite_prompt_with_hints(selected_tag, pattern_name, pattern_description, hints)
                        else:
                            self.improve_prompt(selected_tag, pattern_name, pattern_description, pattern_prompt, hints)
                with improve_col2:
                    if hints.strip():
                        st.success("✅ Ready to apply changes")
                    else:
                        st.info("💭 Enter your improvements above")

    def overwrite_prompt_with_hints(self, selected_tag, pattern_name, pattern_description, hints):
        new_prompt = hints
        st.session_state.pattern_responses[selected_tag] = [pattern_name, pattern_description, new_prompt, False]
        st.success(f"Prompt for tag '{selected_tag}' has been overwritten.")

    def improve_prompt(self, selected_tag, pattern_name, pattern_description, pattern_prompt, hints):
        improved_prompt = f"{pattern_prompt}\n\nHints for improvement:\n{hints}"
        st.session_state.pattern_responses[selected_tag] = [pattern_name, pattern_description, improved_prompt, False]
        st.success(f"Prompt for tag '{selected_tag}' has been improved.")
