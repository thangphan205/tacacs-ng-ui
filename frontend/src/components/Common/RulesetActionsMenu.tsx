import { IconButton } from "@chakra-ui/react"
import { BsThreeDotsVertical } from "react-icons/bs"
import type { RulesetPublic } from "@/client"
import DeleteRuleset from "../Rulesets/DeleteRuleset"
import EditRuleset from "../Rulesets/EditRuleset"
import { MenuContent, MenuRoot, MenuTrigger } from "../ui/menu"

interface RulesetActionsMenuProps {
  ruleset: RulesetPublic
}

export const RulesetActionsMenu = ({ ruleset }: RulesetActionsMenuProps) => {
  return (
    <MenuRoot>
      <MenuTrigger asChild>
        <IconButton variant="ghost" color="inherit">
          <BsThreeDotsVertical />
        </IconButton>
      </MenuTrigger>
      <MenuContent>
        <EditRuleset ruleset={ruleset} />
        <DeleteRuleset ruleset={ruleset} />
      </MenuContent>
    </MenuRoot>
  )
}
